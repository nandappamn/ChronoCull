#!/usr/bin/env python3
"""
Scientific Research Query Utility
Fetches scientific publications via NCBI E-utilities (PubMed) or arXiv API.
"""
import sys
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import argparse

def search_pubmed(query: str, max_results: int = 5):
    print(f"[scientific-research] Searching PubMed for: '{query}' (limit={max_results})")
    base_esearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance"
    }
    url = f"{base_esearch}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AntigravityAgent/1.0 (mailto:agent@example.com)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            id_list = data.get("esearchresult", {}).get("idlist", [])
            
        if not id_list:
            print("[scientific-research] No PubMed records found.")
            return []
            
        print(f"[scientific-research] Found PMIDs: {id_list}")
        base_esummary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        sum_url = f"{base_esummary}?{urllib.parse.urlencode(summary_params)}"
        req2 = urllib.request.Request(sum_url, headers={"User-Agent": "AntigravityAgent/1.0"})
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            sum_data = json.loads(resp2.read().decode())
            results = sum_data.get("result", {})
            
        articles = []
        for pmid in id_list:
            doc = results.get(pmid, {})
            title = doc.get("title", "No title")
            pubdate = doc.get("pubdate", "Unknown date")
            source = doc.get("source", "Unknown journal")
            authors = [a.get("name", "") for a in doc.get("authors", [])]
            print(f"\n[PMID: {pmid}] {title}")
            print(f"  Journal: {source} ({pubdate})")
            print(f"  Authors: {', '.join(authors[:3])} et al.")
            articles.append({"pmid": pmid, "title": title, "journal": source, "date": pubdate})
        return articles
    except Exception as e:
        print(f"[scientific-research] Network or query error: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Query PubMed for scientific research literature")
    parser.add_argument("--query", type=str, required=True, help="Scientific search terms")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum number of articles")
    args = parser.parse_args()

    search_pubmed(args.query, args.max_results)

if __name__ == "__main__":
    main()
