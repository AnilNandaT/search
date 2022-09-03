import json
from time import time
from typing import List, Any, Dict, Iterable
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from tqdm.auto import tqdm, trange

from src.data.resources.base_resource import BaseResource


class CrossrefResource(BaseResource):
    db_name = "Crossref"
    def __init__(self):
        super().__init__()
        self.limit = 25000

    # @property
    # @classmethod
    # def db_name(self) -> str:
    #     return "Crossref"

    @classmethod
    def id_to_url(self, article_id: str):
        return f"https://www.doi.org/{article_id}"

    def get_ids_by_query(self, query: str, collecting: bool = False) -> List[str]:
        """Using Bio.Entrez module, get PMIDs from PubMed
        corresponding to a search term.

        Args:
            query (str): A term that will be queried to PubMed.

        Returns:
            List[int]: Corresponding PMIDs.

        """
        start = time()
        result_dois = []
        response_len = 1
        offset = 0
        while offset < self.limit:
            params={
                "query": query,
                "rows": 1000,
                "mailto": "yury@prepaire.com",
                "offset": offset
            }
            params_str = urlencode(params, doseq=True)
            cgi = "https://api.crossref.org/works"
            try:
                handle = urlopen(Request(
                    cgi,
                    data=params_str.encode("utf8"),
                    method="GET"
                )).read()

                data = json.loads(handle.decode('utf-8'))
            except Exception as e:
                print(repr(e))
                continue

            items = data["message"]["items"]
            if len(items) == 0:
                break
            else:
                offset += 1000

            dois = [item.get("DOI") for item in items]
            titles = [item.get("title", [None])[0] for item in items]
            urls = [item.get("URL") for item in items]

            self.db.add_titles_info(
                dois,
                self.db_name,
                urls,
                titles,
                [None] * len(dois)
            )

            result_dois += dois
        print("DOIs: {:.2f}".format(time()-start))

        return result_dois

    def get_info_by_ids(self, ids: List[str]) -> Iterable[Dict[str, List[Any]]]:
        return [{
            "pmids": [],
            "titles": [],
            "urls": [],
            "pmcids": []
        }]
