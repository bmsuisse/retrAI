"""Messy module — intentionally full of lint violations."""

import os, sys, json
import  math
from datetime import datetime,timedelta

GLOBAL_VAR =42
unused_import = os

def  calculate_area(shape,dimensions):
  if shape=="circle":
        r=dimensions[0]
        return math.pi*r**2
  elif shape ==  "rectangle":
        w=dimensions[0]
        h=dimensions[1]
        return w*h
  elif shape == "triangle":
        b=dimensions[0]
        h=dimensions[1]
        return 0.5*b*h
  else:
     return None

class   ShoppingCart:
     def __init__(self):
        self.items=[]
        self.discount=0

     def add_item(self,name,price,qty=1):
        item = {"name":name ,"price": price,"qty":qty}
        self.items.append(item)

     def  total(self):
        t = 0
        for item  in self.items:
            t+=item["price"]*item["qty"]
        t = t*(1-self.discount /100)
        return t

     def remove_item(self , name):
        self.items = [i for i in self.items if  i["name"]!=name]

     def apply_discount(self,pct):
        self.discount=pct


def  parse_date(s):
     """Parse date from various formats."""
     formats = ["%Y-%m-%d","%d/%m/%Y","%m-%d-%Y","%Y%m%d"]
     for  fmt  in formats:
            try:
                return datetime.strptime(s,fmt)
            except ValueError:
                  continue
     raise ValueError(f"Cannot parse date: {s}")


def  fibonacci_gen(n):
      a,b = 0,1
      for _ in range(n):
            yield a
            a , b=b , a+b


def  process_data(data):
      result=[]
      for  d in data:
        if d>0:
            result.append(d**2)
        elif d ==0:
                result.append(0)
        else:
              result.append(-d)
      return result

class Logger:
  level = "INFO"
  def __init__(self,name):
     self.name=name
     self.entries =[]
  def log(self,msg,level = None):
      if level is  None:
        level = self.level
      entry = {"ts":datetime.now().isoformat(),"level":level,"msg":msg,"logger":self.name}
      self.entries.append(entry)
      print(f"[{level}] {self.name}: {msg}")
  def dump(self):
      return json.dumps(self.entries,indent=2)

x=lambda a,b:a+b
y = lambda a: a*2
