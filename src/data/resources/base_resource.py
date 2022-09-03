import os
from typing import List, Any, Dict, Iterable
from abc import ABCMeta, abstractmethod

import pandas as pd
from tqdm.auto import tqdm, trange

from src.data.utils.lite import DatabaseConnector
from src.data.utils.io import load_json, save_json
from src.config import (
    DRUGS_DF_PATH,
    TARGETS_DF_PATH
)

USELESS_DATA_PATH = "src/data/"

class BaseResource(metaclass = ABCMeta):
    def __init__(self):
        self.db = DatabaseConnector()
        self.drugs_df = self.load_and_preprocess_df(DRUGS_DF_PATH, "drugbank_id")
        self.targets_df = self.load_and_preprocess_df(TARGETS_DF_PATH, "uniprot_id")

    # @property
    # @classmethod
    # @abstractmethod
    # def db_name(self) -> str:
    #     pass

    @classmethod
    @abstractmethod
    def id_to_url(self, article_id: str):
        pass

    def load_and_preprocess_df(self, path: str, id_field: str) -> pd.DataFrame:
        """Load and preprocess DataFrame.

        Args:
            path (str): Path to .csv file.
            id_field (str): Name of the "id" field in the frame.

        Returns:
            pd.DataFrame: Preprocessed DataFrame.

        """
        df = pd.read_csv(path)
        df[id_field] = df[id_field].map(str)

        return df

    @abstractmethod
    def get_ids_by_query(self, query: str, collecting: bool = False) -> List[str]:
        pass

    @abstractmethod
    def get_info_by_ids(self, ids: List[str]) -> Iterable[Dict[str, List[Any]]]:
        pass

    def get_useless_items(self):
        path = os.path.join(USELESS_DATA_PATH, f"{self.db_name}_useless.json")
        if os.path.exists(path):
            return load_json(path)
        else:
            return []

    def add_useless_item(self, item_id: str):
        useless = self.get_useless_items()
        useless.append(item_id)
        save_json(useless, os.path.join(USELESS_DATA_PATH, f"{self.db_name}_useless.json"))

    def make_items_list(self):
        items = []

        items += [
            {
                "name": row["name"],
                "id": row["drugbank_id"],
                "type": "drug"
            }
            for i, row in self.drugs_df.iterrows()
            if row["type"] == "SmallMoleculeDrug" and \
            row["state"] == "solid"
        ]

        items += [
            {
                "name": row["name"],
                "id": row["uniprot_id"],
                "type": "target"
            }
            for i, row in self.targets_df.iterrows()
        ]

        return items

    def insert_ids_items(self):
        """Get PMIDs corresponding to each item name and update database.

        Returns:
            None

        """
        items = self.make_items_list()
        print(len(items))
        known_items = self.db.get_known_item_ids(self.db_name)
        print(len(known_items))
        items = [i for i in items if i["id"] not in known_items]
        print(len(items))
        items = [i for i in items if i["id"] not in self.get_useless_items()]
        print(len(items))

        for item in tqdm(items, desc="Items collection"):
            ids = self.get_ids_by_query(item["name"], collecting=True)
            if len(ids) == 0:
                self.add_useless_item(item["id"])

            self.db.add_article_items(
                ids,
                self.db_name,
                [item["id"]] * len(ids),
                [item["type"]] * len(ids)
            )

    def insert_article_info(self):
        unknown_pmids = self.db.get_unknown_info_pmids(self.db_name)
        for info in self.get_info_by_ids(unknown_pmids):
            self.db.add_titles_info(
                info["pmids"],
                self.db_name,
                info["urls"],
                info["titles"],
                info["pmcids"]
            )
