"""Tests for bio_search tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from retrai.tools.bio_search import (
    _search_chembl,
    _search_clinicaltrials,
    _search_pdb,
    _search_pubmed,
    _search_uniprot,
    bio_search,
)


class TestBioSearchTool:
    def test_schema_has_required_fields(self) -> None:
        from retrai.tools.builtins import BioSearchTool

        tool = BioSearchTool()
        schema = tool.get_schema()
        assert schema.name == "bio_search"
        assert "source" in schema.parameters["properties"]
        assert "query" in schema.parameters["properties"]
        assert schema.parameters["required"] == ["source", "query"]

    def test_parallel_safe(self) -> None:
        from retrai.tools.builtins import BioSearchTool

        tool = BioSearchTool()
        assert tool.parallel_safe is True

    @pytest.mark.asyncio
    async def test_unknown_source_returns_error(self) -> None:
        result = await bio_search(source="unknown_db", query="test")
        assert "Unknown source" in result
        assert "pubmed" in result

    @pytest.mark.asyncio
    async def test_pubmed_search_error_handling(self) -> None:
        with patch(
            "retrai.tools.bio_search._http_get", side_effect=Exception("Network error")
        ):
            result = await bio_search(source="pubmed", query="KRAS G12C")
        assert "error" in result.lower()

    def test_pubmed_no_results(self) -> None:
        mock_response = json.dumps({"esearchresult": {"idlist": []}})
        with patch("retrai.tools.bio_search._http_get", return_value=mock_response):
            result = _search_pubmed("nonexistent query xyz", 10)
        assert "No results found" in result

    def test_pubmed_with_results(self) -> None:
        search_response = json.dumps(
            {"esearchresult": {"idlist": ["12345678", "87654321"]}}
        )
        fetch_response = "Abstract text for PMID 12345678\n\nAbstract text for 87654321"
        summary_response = json.dumps(
            {
                "result": {
                    "uids": ["12345678"],
                    "12345678": {
                        "title": "KRAS G12C inhibitor sotorasib",
                        "authors": [{"name": "Smith J"}, {"name": "Jones A"}],
                        "source": "Nature Medicine",
                        "pubdate": "2021",
                    },
                }
            }
        )
        responses = [search_response, fetch_response, summary_response]
        call_count = 0

        def mock_get(url: str, **kwargs) -> str:
            nonlocal call_count
            result = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return result

        with patch("retrai.tools.bio_search._http_get", side_effect=mock_get):
            result = _search_pubmed("KRAS G12C", 5)

        assert "PubMed Results" in result
        assert "12345678" in result

    def test_clinicaltrials_no_results(self) -> None:
        mock_response = json.dumps({"studies": [], "totalCount": 0})
        with patch("retrai.tools.bio_search._http_get", return_value=mock_response):
            result = _search_clinicaltrials("nonexistent", 5)
        assert "No results" in result

    def test_clinicaltrials_with_results(self) -> None:
        mock_response = json.dumps(
            {
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {
                                "nctId": "NCT12345678",
                                "briefTitle": "KRAS G12C Phase 3 Trial",
                            },
                            "statusModule": {"overallStatus": "RECRUITING"},
                            "descriptionModule": {"briefSummary": "Testing sotorasib."},
                            "designModule": {"phases": ["PHASE3"]},
                        }
                    }
                ],
                "totalCount": 1,
            }
        )
        with patch("retrai.tools.bio_search._http_get", return_value=mock_response):
            result = _search_clinicaltrials("KRAS G12C", 5)

        assert "NCT12345678" in result
        assert "PHASE3" in result

    def test_uniprot_no_results(self) -> None:
        mock_response = json.dumps({"results": []})
        with patch("retrai.tools.bio_search._http_get", return_value=mock_response):
            result = _search_uniprot("nonexistent", 5)
        assert "No results" in result

    def test_chembl_no_results(self) -> None:
        mock_response = json.dumps({"targets": [], "molecules": []})
        with patch("retrai.tools.bio_search._http_get", return_value=mock_response):
            result = _search_chembl("nonexistent", 5)
        assert "No results" in result

    def test_pdb_no_results(self) -> None:
        mock_response = json.dumps({"result_set": [], "total_count": 0})

        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_response.encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _search_pdb("nonexistent", 5)
        assert "No structures found" in result

    @pytest.mark.asyncio
    async def test_save_path(self, tmp_path: Path) -> None:
        mock_response = json.dumps({"esearchresult": {"idlist": []}})
        with patch("retrai.tools.bio_search._http_get", return_value=mock_response):
            result = await bio_search(
                source="pubmed",
                query="test",
                save_path="output/results.md",
                cwd=str(tmp_path),
            )
        saved = tmp_path / "output" / "results.md"
        assert saved.exists()
        assert "Saved to" in result
