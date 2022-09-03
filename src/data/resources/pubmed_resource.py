import os
import sys
import json
if sys.path[0].endswith("/src/data/resources"):
    sys.path.append(sys.path[0].split("/src/data/resources")[0])
from typing import List, Any, Dict, Iterable
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from datetime import datetime

from Bio import Entrez
from tqdm.auto import tqdm, trange

from src.data.resources.base_resource import BaseResource
from src.config import ENTREZ_EMAIL, PUBMED_API_KEY, SERVER_DUMPS_PATH


Entrez.email = ENTREZ_EMAIL
Entrez.api_key = PUBMED_API_KEY

class PubMedResource(BaseResource):
    db_name = "PubMed"
    def __init__(self):
        super().__init__()
        self.api_key = PUBMED_API_KEY
        self.retmax = 25000
        self.chunk_size = 10000

    @classmethod
    def id_to_url(self, article_id: str):
        return f"https://pubmed.ncbi.nlm.nih.gov/{article_id}/"

    def get_ids_by_query(self, query: str, collecting: bool = False) -> List[str]:
        """Using Bio.Entrez module, get PMIDs from PubMed
        corresponding to a search term.

        Args:
            query (str): A term that will be queried to PubMed.
            collecting (bool): Set to True if you are running it from a
                data collection script.

        Returns:
            List[int]: Corresponding PMIDs.

        """
        if collecting:
            query = f'"{query}"[All Fields]'

        params={
            "db": "pubmed",
            "term": query,
            "api_key": self.api_key,
            "retmax": self.retmax
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

    def get_records_esummary(self, ids: List[str]):
        params={
            "db": "pubmed",
            "id": ','.join(ids),
            "api_key": self.api_key
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

        return records

    def get_records_efetch(self, ids: List[str]):
        params={
            "db": "pubmed",
            "id": ','.join(ids),
            "api_key": self.api_key,
            "retmode": "xml"
        }
        params_str = urlencode(params, doseq=True)
        cgi = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

        handle = urlopen(Request(
            cgi,
            data=params_str.encode("utf8"),
            method="POST"
        ))

        records = Entrez.read(handle)
        handle.close()

        return records

    def _get_info_by_ids(self, ids: List[str]) -> Dict[str, List[Any]]:
        records = self.get_records_esummary(ids)
        titles = [r["Title"] for r in records]
        pmcids = [r["ArticleIds"].get("pmc") for r in records]

        info = {
            "pmids": ids,
            "titles": titles,
            "urls": [None] * len(ids),
            "pmcids": pmcids
        }

        return info

    def get_info_by_ids(self, ids: List[str]) -> Iterable[Dict[str, List[Any]]]:
        ids_copy = ids.copy()
        for i in trange(0, len(ids_copy), self.chunk_size, desc="Info collection"):
            while True:
                try:
                    info_batch = self._get_info_by_ids(ids[i:i+self.chunk_size])
                    yield info_batch

                    break
                except Exception as e:
                    print(repr(e))
                    # rarely there are articles that raise an error
                    # we just remove them
                    if str(e).startswith("UID="):
                        ids_copy.remove(str(e).split(":")[0].split("=")[-1])
                    continue

    def get_dump(self):
        today = datetime.today().strftime("%Y-%m-%d")
        save_path = os.path.join(
            SERVER_DUMPS_PATH,
            f"pubmed_{today}.jsonl",
        )
        ids = self.db.get_unique_pmids(self.db_name)
        for i in trange(0, len(ids), self.chunk_size, desc="Dump collection"):
            while True:
                try:
                    records = self.get_records_efetch(ids[i:i+self.chunk_size])
                    abstracts = [
                        "\n".join(r["MedlineCitation"]["Article"]["Abstract"]["AbstractText"])
                        if "Abstract" in r["MedlineCitation"]["Article"].keys()
                        else ""
                        for r in records["PubmedArticle"]
                    ]

                    titles = [
                        r["MedlineCitation"]["Article"]["ArticleTitle"]
                        for r in records["PubmedArticle"]
                    ]

                    with open(save_path, "a") as fp:
                        for i, (a, title, pmid) in enumerate(zip(
                            abstracts,
                            titles,
                            ids[i:i+self.chunk_size]
                        )):
                            fp.write(json.dumps({
                                "abstract": a,
                                "title": title,
                                "doi": pmid
                            }))
                            fp.write(os.linesep)

                    break
                except Exception as e:
                    print(repr(e))
                    # rarely there are articles that raise an error
                    # we just remove them
                    if str(e).startswith("UID="):
                        ids_copy.remove(str(e).split(":")[0].split("=")[-1])
                    continue
