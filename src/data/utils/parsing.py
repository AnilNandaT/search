import os
import sys
if sys.path[0].endswith("/src/data/utils"):
    sys.path.append(sys.path[0].split("/src/data/utils")[0])
import requests
import json
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from collections import defaultdict

from typing import List, Dict, Any
from tqdm.auto import tqdm, trange
from argparse import ArgumentParser
import pandas as pd
import sqlite3
from Bio import Entrez

from src.data.utils.io import load_pkl, save_pkl, save_json, load_json
from src.data.utils.lite import DatabaseConnector
from src.config import (
    DRUGS_DF_PATH,
    DRUGS_PMID_MAP_PATH,
    TARGETS_DF_PATH,
    TARGETS_PMID_MAP_PATH,
    ENTREZ_EMAIL,
    PMID_INFO_PATH,
    ARTICLE_DATABASE,
    PUBMED_API_KEY
)

Entrez.email = ENTREZ_EMAIL
Entrez.api_key = PUBMED_API_KEY

def get_pmids_by_term(term: str) -> List[int]:
    """Using Bio.Entrez module, get PMIDs from PubMed
    corresponding to a search term.

    Args:
        term (str): A term that will be queried to PubMed.

    Returns:
        List[int]: Corresponding PMIDs.

    """
    params={
        "db": "pubmed",
        "term": term,
        "api_key": PUBMED_API_KEY,
        "retmax": 25000
    }
    params_str = urlencode(params, doseq=True)
    cgi = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    handle = urlopen(Request(
        cgi,
        data=params_str.encode("utf8"),
        method="POST"
    ))

    record = Entrez.read(handle)
    handle.close()

    return list(map(str, record["IdList"]))


def get_articles_info(
    pmids: List[int],
    infos: Dict[int, Any],
    to_db: bool = False
) -> None:
    """Get info for the list of articles. The info will be returned to the
    `infos` dict.

    Args:
        pmids (List[int]): PubMed PMIDs (no more than 10_000 per once).
        infos (Dict[int, Any]): A dictionary containing articles' information.
            It will be updated with new items.

    Returns:
        None

    """
    handle = Entrez.esummary(
        db="pubmed",
        id=','.join(map(str, pmids)) # pass multiple pmids separated with ","
    )
    records = Entrez.read(handle)
    handle.close()

    assert len(records) == len(pmids)

    if to_db:
        titles = [r["Title"] for r in records]
        pmcids = [r["ArticleIds"].get("pmc") for r in records]

        conn = sqlite3.connect(PMID_ITEM_DATABASE)
        cursor = conn.cursor()

        add_titles_info(pmids, titles, pmcids, cursor)

        conn.commit()
        conn.close()
    else:
        for r, pmid in zip(records, pmids):
            infos[pmid] = {
                "t": r["Title"],
                "pmc": r["ArticleIds"].get("pmc")
            }

def get_articles_info_custom(
    pmids: List[int],
    infos: Dict[int, Any],
    to_db: bool = False,
    mode: str = "xml"
) -> None:
    """Get info for the list of articles. The info will be returned to the
    `infos` dict.

    Args:
        pmids (List[int]): PubMed PMIDs (no more than 10_000 per once).
        infos (Dict[int, Any]): A dictionary containing articles' information.
            It will be updated with new items.

    Returns:
        None

    """
    if mode == "xml":
        params={
            "db": "pubmed",
            "id": ','.join(pmids),
            "api_key": PUBMED_API_KEY
        }
        params_str = urlencode(params, doseq=True)
        cgi = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

        handle = urlopen(Request(
            cgi,
            data=params_str.encode("utf8"),
            method="POST"
        ))

        records = Entrez.read(handle)
        handle.close()

        assert len(records) == len(pmids)

        if to_db:
            titles = [r["Title"] for r in records]
            pmcids = [r["ArticleIds"].get("pmc", "NULL") for r in records]

            conn = sqlite3.connect(PMID_ITEM_DATABASE)
            cursor = conn.cursor()

            add_titles_info(pmids, titles, pmcids, cursor)

            conn.commit()
            conn.close()
        else:
            for r, pmid in zip(records, pmids):
                infos[pmid] = {
                    "t": r["Title"],
                    "pmc": r["ArticleIds"].get("pmc")
                }

    elif mode == "json":
        params={
            "db": "pubmed",
            "id": ','.join(pmids),
            "retmode": "json",
            "api_key": PUBMED_API_KEY
        }
        params_str = urlencode(params, doseq=True)

        cgi = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

        # request = Request(cgi, data=params_str.encode("utf8"), method="POST")
        records = requests.post(
            cgi,
            data=params_str.encode("utf8")
        ).json()

        # print(records)

        results = records["result"]

        if to_db:
            titles = [results[str(pmid)]["title"] for pmid in pmids]
            pmcids = [
                aid["value"] if aid["idtype"] == "pmc" else None
                for pmid in pmids
                for aid in results[str(pmid)]["articleids"]
            ]

            conn = sqlite3.connect(PMID_ITEM_DATABASE)
            cursor = conn.cursor()

            add_titles_info(pmids, titles, pmcids, cursor)

            conn.commit()
            conn.close()
        else:
            for r, pmid in zip(records, pmids):
                pmc_id = [
                    aid["value"]
                    for aid in results[str(pmid)]["articleids"]
                    if aid["idtype"] == "pmc"
                ]

                infos[pmid] = {
                    "t": results[str(pmid)]["title"],
                    "pmc": pmc_id[0] if len(pmc_id) > 0 else ""
                }



def batched_get_articles_info(pmids: List[int]) -> List[Dict[str, Any]]:
    """Get articles info as a list of dicts.

    Args:
        pmids (List[int]): PubMed PMIDs.

    Returns:
        List[Dict[str, Any]]: List of articles' info.

    """
    infos = dict()
    chunk_size = 10_000
    for i in trange(0, len(pmids), chunk_size):
        get_articles_info(pmids[i:i+chunk_size], infos)

    results = [infos[k] for k in pmids]

    return results


class ParserPMID:
    """PubMed Parser"""
    def __init__(self):
        self.drugs_pmid_dbid_map = defaultdict(list)
        self.targets_pmid_dbid_map = defaultdict(list)
        self.pmid_info = defaultdict(int)

    def load_maps(self):
        self.drugs_pmid_dbid_map = load_pkl(DRUGS_PMID_MAP_PATH)
        self.targets_pmid_dbid_map = load_pkl(TARGETS_PMID_MAP_PATH)

    def fill_drugs_pmid_table(self, df: pd.DataFrame) -> None:
        """Get PMIDs corresponding to each drug name and update `drugs_pmid_dbid_map`.
        At the end saves `drugs_pmid_dbid_map` to DRUGS_PMID_MAP_PATH pickle.

        Args:
            df (pd.DataFrame): DataFrame containing drug information.
                Must have `drugbank_id` and `name` fields.

        Returns:
            None

        """
        conn = sqlite3.connect(PMID_ITEM_DATABASE)

        for i, row in tqdm(df.iterrows(), total=len(df)):
            pmids = get_pmids_by_term(f'"{row["name"]}"[All Fields]')

            cursor = conn.cursor()
            add_item_pmids(
                pmids,
                [row["drugbank_id"]] * len(pmids),
                ["drug"] * len(pmids)
            )
            conn.commit()

        conn.close()

    def fill_targets_pmid_table(self, df: pd.DataFrame) -> None:
        """Get PMIDs corresponding to each target name and update `targets_pmid_dbid_map`.
        At the end saves `targets_pmid_dbid_map` to TARGETS_PMID_MAP_PATH pickle.

        Args:
            df (pd.DataFrame): DataFrame containing target information.
                Must have `uniprot_id` and `name` fields.

        Returns:
            None

        """
        conn = sqlite3.connect(PMID_ITEM_DATABASE)

        for i, row in tqdm(df.iterrows(), total=len(df)):
            pmids = get_pmids_by_term(f'"{row["name"]}"[All Fields]')

            cursor = conn.cursor()
            add_item_pmids(
                pmids,
                [row["uniprot_id"]] * len(pmids),
                ["target"] * len(pmids)
            )
            conn.commit()

        conn.close()

    def fill_pmid_tables(self) -> None:
        """A wrapper around drugs and targets extraction.

        Returns:
            None

        """
        drugs_df = pd.read_csv(DRUGS_DF_PATH)
        targets_df = pd.read_csv(TARGETS_DF_PATH)

        self.fill_drugs_pmid_table(drugs_df)
        self.fill_targets_pmid_table(targets_df)

    def get_popular_keys(self, d):
        return [k for k, v in d.items() if len(v) > 0]

    def get_pmids_info(self):
        chunk_size = 10000

        keys = get_unknown_info_pmids()
        print(f"Total keys to parse: {len(keys)}")

        for i in trange(0, len(keys), chunk_size):
            while True:
                try:
                    get_articles_info_custom(
                        keys[i:i+chunk_size],
                        self.pmid_info,
                        to_db=True,
                        mode="xml"
                    )
                    break
                except Exception as e:
                    print(str(e))
                    if str(e).startswith("UID="):
                        keys.remove(str(e).split(":")[0].split("=")[-1])
                    continue

    def populate_popular_queries(self):
        POPULAR_QUERIES = [
            "sars-cov-2",
            "covid-19",
            "covid",
            "Dengue",
            "HIV",
            "Ebola",
            "Lassa Fever",
            "H1N1",
            "Monkey Pox",
            "small pox",
            "favipiravir"
        ]
        conn = sqlite3.connect(PMID_ITEM_DATABASE)
        for q in tqdm(POPULAR_QUERIES):
            while True:
                try:
                    pmids = get_pmids_by_term(q)
                    break
                except:
                    continue
            cursor = conn.cursor()
            add_popular_query(q, json.dumps(pmids), cursor)
            conn.commit()
        conn.close()


if __name__ == '__main__':
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser')

    parser_a = subparsers.add_parser('articles')
    parser_info = subparsers.add_parser('pmid_info')
    parser_pop = subparsers.add_parser('populate')

    args = parser.parse_args()

    if args.subparser == "articles":
        pmid_parser = ParserPMID()
        pmid_parser.fill_pmid_tables()
    elif args.subparser == "pmid_info":
        pmid_parser = ParserPMID()
        pmid_parser.get_pmids_info()
    elif args.subparser == "populate":
        pmid_parser = ParserPMID()
        pmid_parser.populate_popular_queries()
