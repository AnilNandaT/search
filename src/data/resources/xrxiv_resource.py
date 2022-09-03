import json
from time import time
from typing import List, Any, Dict, Iterable
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from tqdm.auto import tqdm, trange

from src.data.utils.xrxiv_query import XRXivQuery
from src.data.resources.base_resource import BaseResource
from src.config import SERVER_DUMPS_PATH


class XrxivResource(BaseResource):
    db_name = "Xrxiv"
    def __init__(self):
        super().__init__()
        self.querier = XRXivQuery(SERVER_DUMPS_PATH)

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
        if isinstance(query, str):
            query = [query]

        df = self.querier.search_keywords(query)
        dois = df["doi"].to_list()
        titles = df["title"].to_list()
        urls = [None] * len(df)

        if collecting:
            self.db.add_titles_info(
                dois,
                self.db_name,
                urls,
                titles,
                [None] * len(dois)
            )

        return list(map(str, dois))

    def get_info_by_ids(self, ids: List[str]) -> Iterable[Dict[str, List[Any]]]:
        return [{
            "pmids": [],
            "titles": [],
            "urls": [],
            "pmcids": []
        }]
