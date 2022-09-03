"""Query dumps from bioRxiv and medRXiv."""
import logging
import os
import sys
from typing import List, Union

import pandas as pd

from src.data.utils.processing import preprocess_query

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


class XRXivQuery:
    """Query class."""

    def __init__(
        self,
        dump_path: str,
        fields: List[str] = ["title", "doi", "abstract"],
    ):
        """
        Initialize the query class.

        Args:
            dump_path (str): path to the dump to be queried.
            fields (List[str], optional): fields to contained in the dump per paper.
                Defaults to ['title', 'doi', 'authors', 'abstract', 'date', 'journal'].
        """
        self.dump_path = dump_path
        self.fields = fields
        self.errored = False

        # try:
        self.df = pd.concat([
            pd.read_json(os.path.join(dump_path, file), lines=True)
            for file in os.listdir(self.dump_path)
        ], ignore_index=True)

        self.df = self.df.drop_duplicates("doi")
        self.df = self.df.reset_index(drop=True)

        # self.df["date"] = [date.strftime("%Y-%m-%d") for date in self.df["date"]]
        self.tokens_df = self.df.copy()
        fields = [field for field in self.fields if field != "date"]
        for field in fields:
            self.tokens_df[field] = self.tokens_df[field].map(str)
            self.tokens_df[field] = self.tokens_df[field].map(self.tokenize)
        # except ValueError as e:
        #     logger.warning(f"Problem in reading file {os.path.join(dump_path, file)}: {e} - Skipping!")
        #     self.errored = True
        # except KeyError as e:
        #     logger.warning(f"Key {e} missing in file from {os.path.join(dump_path, file)} - Skipping!")
        #     self.errored = True

    def tokenize(self, text: str):
        text = preprocess_query(text)
        tokens = text.split()

        return tokens

    def search_keywords(
        self,
        keywords: List[Union[str, List[str]]],
        fields: List[str] = None,
        output_filepath: str = None,
    ) -> List[dict]:
        """
        Search for papers in the dump using keywords.

        Args:
            keywords (List[str, List[str]]): Items will be AND separated. If items
                are lists themselves, they will be OR separated.
            fields (List[str], optional): fields to be used in the query search.
                Defaults to None, a.k.a. search in all fields excluding date.
            output_filepath (str, optional): optional output filepath where to store
                the hits in JSONL format. Defaults to None, a.k.a., no export to a file.

        Returns:
            List[dict]: a list of papers associated to the query.
        """
        if fields is None:
            fields = self.fields
        fields = [field for field in fields if field != "date"]
        hits_per_field = []
        for field in fields:
            field_data = self.tokens_df[field]
            hits_per_keyword = []
            for keyword in keywords:
                query = self.tokenize(keyword)
                hits_per_keyword.append(field_data.map(lambda x: all(q in x for q in query)))
            if len(hits_per_keyword):
                keyword_hits = hits_per_keyword[0]
                for single_keyword_hits in hits_per_keyword[1:]:
                    keyword_hits &= single_keyword_hits
                hits_per_field.append(keyword_hits)
        if len(hits_per_field):
            hits = hits_per_field[0]
            for single_hits in hits_per_field[1:]:
                hits |= single_hits
        if output_filepath is not None:
            self.df[hits].to_json(output_filepath, orient="records", lines=True)
        return self.df[hits]
