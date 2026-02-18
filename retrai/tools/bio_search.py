"""Bio search tool — search biomedical databases.

Supports:
  - PubMed (NCBI E-utilities)
  - ClinicalTrials.gov (REST API v2)
  - UniProt (REST API — proteins, disease associations)
  - ChEMBL (REST API — drug targets, bioactivity)
  - PDB (RCSB REST API — protein structures)
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT = 30  # seconds


def _http_get(url: str, headers: dict[str, str] | None = None) -> str:
    """Simple HTTP GET returning response body as text."""
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "retrAI/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _search_pubmed(query: str, max_results: int) -> str:
    """Search PubMed via NCBI E-utilities."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    # Step 1: esearch to get PMIDs
    search_url = (
        f"{base}/esearch.fcgi?db=pubmed&term={urllib.parse.quote(query)}"
        f"&retmax={max_results}&retmode=json&sort=relevance"
    )
    try:
        data = json.loads(_http_get(search_url))
        ids = data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        return f"PubMed search error: {e}"

    if not ids:
        return f"PubMed: No results found for '{query}'"

    # Step 2: efetch to get abstracts
    ids_str = ",".join(ids[:max_results])
    fetch_url = f"{base}/efetch.fcgi?db=pubmed&id={ids_str}&rettype=abstract&retmode=text"
    try:
        abstracts = _http_get(fetch_url)
    except Exception as e:
        abstracts = f"(Could not fetch abstracts: {e})"

    # Step 3: esummary for structured metadata
    summary_url = f"{base}/esummary.fcgi?db=pubmed&id={ids_str}&retmode=json"
    results: list[dict[str, Any]] = []
    try:
        summary_data = json.loads(_http_get(summary_url))
        uids = summary_data.get("result", {}).get("uids", [])
        for uid in uids:
            article = summary_data["result"].get(uid, {})
            results.append(
                {
                    "pmid": uid,
                    "title": article.get("title", ""),
                    "authors": [
                        a.get("name", "") for a in article.get("authors", [])[:5]
                    ],
                    "journal": article.get("source", ""),
                    "pub_date": article.get("pubdate", ""),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                }
            )
    except Exception:
        pass

    output_parts = [f"## PubMed Results for: {query}\n"]
    output_parts.append(f"Found {len(ids)} results (showing {len(results or ids)}):\n")

    if results:
        for r in results:
            authors_str = ", ".join(r["authors"]) if r["authors"] else "Unknown"
            output_parts.append(
                f"- **PMID {r['pmid']}**: {r['title']}\n"
                f"  Authors: {authors_str} | {r['journal']} ({r['pub_date']})\n"
                f"  URL: {r['url']}\n"
            )
    else:
        output_parts.append(f"PMIDs: {', '.join(ids[:max_results])}\n")

    output_parts.append(f"\n## Abstracts\n{abstracts[:8000]}")
    return "\n".join(output_parts)


def _search_clinicaltrials(query: str, max_results: int) -> str:
    """Search ClinicalTrials.gov REST API v2."""
    url = (
        f"https://clinicaltrials.gov/api/v2/studies"
        f"?query.term={urllib.parse.quote(query)}"
        f"&pageSize={min(max_results, 20)}"
        f"&format=json"
    )
    try:
        data = json.loads(_http_get(url))
    except Exception as e:
        return f"ClinicalTrials.gov error: {e}"

    studies = data.get("studies", [])
    if not studies:
        return f"ClinicalTrials.gov: No results for '{query}'"

    output_parts = [f"## ClinicalTrials.gov Results for: {query}\n"]
    output_parts.append(f"Found {data.get('totalCount', len(studies))} studies:\n")

    for study in studies[:max_results]:
        proto = study.get("protocolSection", {})
        id_mod = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        desc_mod = proto.get("descriptionModule", {})
        design_mod = proto.get("designModule", {})

        nct_id = id_mod.get("nctId", "")
        title = id_mod.get("briefTitle", "")
        status = status_mod.get("overallStatus", "")
        phase = design_mod.get("phases", [""])[0] if design_mod.get("phases") else ""
        brief_summary = desc_mod.get("briefSummary", "")[:500]

        output_parts.append(
            f"- **{nct_id}**: {title}\n"
            f"  Status: {status} | Phase: {phase}\n"
            f"  Summary: {brief_summary}\n"
            f"  URL: https://clinicaltrials.gov/study/{nct_id}\n"
        )

    return "\n".join(output_parts)


def _search_uniprot(query: str, max_results: int) -> str:
    """Search UniProt REST API for protein data."""
    url = (
        f"https://rest.uniprot.org/uniprotkb/search"
        f"?query={urllib.parse.quote(query)}"
        f"&format=json"
        f"&size={min(max_results, 25)}"
        f"&fields=accession,protein_name,gene_names,organism_name,function,disease,length"
    )
    try:
        data = json.loads(_http_get(url))
    except Exception as e:
        return f"UniProt error: {e}"

    results = data.get("results", [])
    if not results:
        return f"UniProt: No results for '{query}'"

    output_parts = [f"## UniProt Results for: {query}\n"]
    output_parts.append(f"Found {len(results)} proteins:\n")

    for entry in results[:max_results]:
        accession = entry.get("primaryAccession", "")
        protein_name = (
            entry.get("proteinDescription", {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value", "Unknown")
        )
        genes = entry.get("genes", [])
        gene_name = genes[0].get("geneName", {}).get("value", "") if genes else ""
        organism = entry.get("organism", {}).get("scientificName", "")
        length = entry.get("sequence", {}).get("length", "")

        # Function comment
        comments = entry.get("comments", [])
        function_text = ""
        disease_text = ""
        for c in comments:
            if c.get("commentType") == "FUNCTION" and not function_text:
                texts = c.get("texts", [])
                if texts:
                    function_text = texts[0].get("value", "")[:300]
            if c.get("commentType") == "DISEASE" and not disease_text:
                disease = c.get("disease", {})
                desc = disease.get("description", {}).get("value", "")[:200]
                disease_text = disease.get("diseaseId", "") + ": " + desc

        output_parts.append(
            f"- **{accession}** ({gene_name}): {protein_name}\n"
            f"  Organism: {organism} | Length: {length} aa\n"
            + (f"  Function: {function_text}\n" if function_text else "")
            + (f"  Disease: {disease_text}\n" if disease_text else "")
            + f"  URL: https://www.uniprot.org/uniprotkb/{accession}\n"
        )

    return "\n".join(output_parts)


def _search_chembl(query: str, max_results: int) -> str:
    """Search ChEMBL REST API for drug/target bioactivity data."""
    # Search targets first
    target_url = (
        f"https://www.ebi.ac.uk/chembl/api/data/target/search"
        f"?q={urllib.parse.quote(query)}&format=json&limit={min(max_results, 10)}"
    )
    try:
        target_data = json.loads(_http_get(target_url))
        targets = target_data.get("targets", [])
    except Exception as e:
        targets = []
        logger.debug("ChEMBL target search error: %s", e)

    # Search molecules/compounds
    mol_url = (
        f"https://www.ebi.ac.uk/chembl/api/data/molecule/search"
        f"?q={urllib.parse.quote(query)}&format=json&limit={min(max_results, 10)}"
    )
    try:
        mol_data = json.loads(_http_get(mol_url))
        molecules = mol_data.get("molecules", [])
    except Exception as e:
        molecules = []
        logger.debug("ChEMBL molecule search error: %s", e)

    if not targets and not molecules:
        return f"ChEMBL: No results for '{query}'"

    output_parts = [f"## ChEMBL Results for: {query}\n"]

    if targets:
        output_parts.append(f"### Targets ({len(targets)} found):\n")
        for t in targets[:max_results]:
            chembl_id = t.get("target_chembl_id", "")
            name = t.get("pref_name", "")
            target_type = t.get("target_type", "")
            organism = t.get("organism", "")
            output_parts.append(
                f"- **{chembl_id}**: {name}\n"
                f"  Type: {target_type} | Organism: {organism}\n"
                f"  URL: https://www.ebi.ac.uk/chembl/target_report_card/{chembl_id}/\n"
            )

    if molecules:
        output_parts.append(f"\n### Compounds ({len(molecules)} found):\n")
        for m in molecules[:max_results]:
            chembl_id = m.get("molecule_chembl_id", "")
            synonyms = m.get("molecule_synonyms", [{}])
            name = m.get("pref_name", "") or synonyms[0].get("molecule_synonym", "")
            mol_type = m.get("molecule_type", "")
            props = m.get("molecule_properties", {}) or {}
            mw = props.get("mw_freebase", "")
            alogp = props.get("alogp", "")
            output_parts.append(
                f"- **{chembl_id}**: {name}\n"
                f"  Type: {mol_type} | MW: {mw} | ALogP: {alogp}\n"
                f"  URL: https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/\n"
            )

    return "\n".join(output_parts)


def _search_pdb(query: str, max_results: int) -> str:
    """Search RCSB PDB for protein structures."""
    search_payload = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query},
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": min(max_results, 25)},
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "score", "direction": "desc"}],
        },
    }
    url = "https://search.rcsb.org/rcsbsearch/v2/query"
    try:
        payload_bytes = json.dumps(search_payload).encode()
        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "retrAI/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return f"PDB search error: {e}"

    results = data.get("result_set", [])
    total = data.get("total_count", 0)

    if not results:
        return f"PDB: No structures found for '{query}'"

    # Fetch summary info for each PDB ID
    pdb_ids = [r["identifier"] for r in results[:max_results]]

    output_parts = [f"## PDB Results for: {query}\n"]
    output_parts.append(f"Found {total} structures (showing {len(pdb_ids)}):\n")

    for pdb_id in pdb_ids:
        try:
            entry_url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
            entry_data = json.loads(_http_get(entry_url))
            struct = entry_data.get("struct", {})
            title = struct.get("title", "")
            exptl = entry_data.get("exptl", [{}])
            method = exptl[0].get("method", "") if exptl else ""
            resolution = entry_data.get("refine", [{}])
            res_val = resolution[0].get("ls_d_res_high", "") if resolution else ""
            output_parts.append(
                f"- **{pdb_id}**: {title}\n"
                f"  Method: {method}"
                + (f" | Resolution: {res_val} Å" if res_val else "")
                + f"\n  URL: https://www.rcsb.org/structure/{pdb_id}\n"
            )
        except Exception:
            output_parts.append(
                f"- **{pdb_id}**: URL: https://www.rcsb.org/structure/{pdb_id}\n"
            )

    return "\n".join(output_parts)


async def bio_search(
    source: str,
    query: str,
    max_results: int = 10,
    save_path: str | None = None,
    cwd: str = ".",
) -> str:
    """Search biomedical databases and return structured results.

    Args:
        source: One of 'pubmed', 'clinicaltrials', 'uniprot', 'chembl', 'pdb'
        query: Search query string
        max_results: Maximum number of results to return
        save_path: Optional path to save results (relative to cwd)
        cwd: Working directory for save_path resolution
    """
    import asyncio
    from pathlib import Path

    source = source.lower().strip()
    dispatch: dict[str, Any] = {
        "pubmed": _search_pubmed,
        "clinicaltrials": _search_clinicaltrials,
        "uniprot": _search_uniprot,
        "chembl": _search_chembl,
        "pdb": _search_pdb,
    }

    if source not in dispatch:
        available = ", ".join(dispatch.keys())
        return f"Unknown source '{source}'. Available: {available}"

    # Run in executor to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, dispatch[source], query, max_results
    )

    if save_path:
        full_path = Path(cwd) / save_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(result, encoding="utf-8")
        result += f"\n\n[Saved to {save_path}]"

    return result
