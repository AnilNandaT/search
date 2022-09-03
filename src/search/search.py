from collections import Counter, defaultdict
from time import time
import json
import gc
import sys
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from tqdm.auto import tqdm
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Any

from src.data.resources.utils import query_all_resources
from src.data.utils.lite import DatabaseConnector
from src.data.utils.io import load_pkl, load_json
from src.config import (
    DRUGS_DF_PATH,
    TARGETS_DF_PATH
)

from src.data.resources.pubmed_resource import PubMedResource
from src.data.resources.crossref_resource import CrossrefResource
from src.data.resources.xrxiv_resource import XrxivResource

RESOURCE_MAP = {
    PubMedResource.db_name: PubMedResource,
    CrossrefResource.db_name: CrossrefResource,
    XrxivResource.db_name: XrxivResource
}
# # Profiling utils
# from line_profiler import LineProfiler
# profiler = LineProfiler()
#
# def profile(func):
#     def inner(*args, **kwargs):
#         profiler.add_function(func)
#         profiler.enable_by_count()
#         return func(*args, **kwargs)
#     return inner


class SearchEngine:
    def __init__(self):
        # Connectors
        self.db = DatabaseConnector()
        # DataFrames
        self.drugs_df = self.load_and_preprocess_df(DRUGS_DF_PATH, "drugbank_id")
        self.targets_df = self.load_and_preprocess_df(TARGETS_DF_PATH, "uniprot_id")

        # All-Item Counters
        full_info = self.db.get_counters()

        # Total counts of articles for each drug
        self.drugs_full_info = full_info[
            full_info["item_type"] == "drug"
        ]
        self.drugs_full_info = self.drugs_full_info.set_index("item_id").to_dict("index")
        self.drugs_full_info = dict(zip(
            self.drugs_df.loc[self.drugs_full_info.keys(), "name"],
            self.drugs_full_info.values()
        ))

        # Total counts of articles for each target
        self.targets_full_info = full_info[
            full_info["item_type"] == "target"
        ]
        self.targets_full_info = self.targets_full_info.set_index("item_id").to_dict("index")
        self.targets_full_info = dict(zip(
            self.targets_df.loc[self.targets_full_info.keys(), "name"],
            self.targets_full_info.values()
        ))

        del full_info
        gc.collect()

        # Information about articles
        self.pmid_info = pd.concat([
            chunk
            for chunk in self.db.get_titles([])
        ], ignore_index=True)
        self.pmid_info = self.pmid_info.set_index("pmid").to_dict("index")

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
        # filter drugs list so it only includes
        # small molecules and solild
        if "type" in df.columns:
            df = df[df["type"] == "SmallMoleculeDrug"]
            df = df[df["state"] == "solid"]
        df = df.set_index(id_field)

        return df

    def pkl_map_to_series(self, pickle_map: Dict[int, List[str]]) -> pd.Series:
        """Converts python PMID-item mapping dictionary to pd.Series

        Args:
            pickle_map (Dict[int, List[str]]): PMID-item dictionary.

        Returns:
            pd.Series: Series object.

        """
        series = pd.Series(pickle_map.values(), index=map(str, pickle_map.keys()))
        return series

    def _calculate_items_info(
        self,
        associated_pmids: pd.Series,
        add_pmids_for_each_item: bool=False
    ) -> Dict[str, Any]:
        """Creates dictionary:
        {
            "Drug Name": {
                "counter": (int) count of PMIDs intersecting with query PMIDs,
                "item_pmids": (List[Dict[str, str]]) list of PMIDs intersecting with query PMIDs
            },
            ...
        }
        It will later be used to calculate metrics.

        Args:
            associated_pmids (pd.Series): PMID intersections of query and items.
            add_pmids_for_each_item (bool): Add associated_pmids for each item under
                `item_pmids` field or not. Use `False` if you only need the counters.

        Returns:
            Dict[str, Any]: Counters and PMIDs for each of the items.

        """

        def add_counter(names):
            """Counts item mentions for each PMID.
            """
            for name in set(names):
                if name != "":
                    if item_info.get(name) is None:
                        item_info[name] = {
                            "counter": 1,
                            "item_pmids": []
                        }
                    else:
                        item_info[name]["counter"] += 1

        def add_item_pmids(item_to_pmids):
            """Forms list of PMIDs for each item.
            """
            for k, v in item_info.items():
                item_info[k]["item_pmids"] = []
                for pmid in item_to_pmids[k]:
                    if k != "":
                        article_info = self.pmid_info.get(pmid)
                        if article_info is not None:
                            title = article_info["title"]
                            db_name = article_info["db_name"]
                            url = article_info["url"]

                            if url is None:
                                url = RESOURCE_MAP[db_name].id_to_url(pmid)

                            has_pdf = (
                                (article_info['pmcid'] != "NULL") and
                                (article_info['pmcid'] is not None)
                            )
                            if has_pdf:
                                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article_info['pmcid']}/pdf"
                            else:
                                pdf_url = ""
                        else:
                            title = ""
                            db_name = ""
                            url = ""
                            has_pdf = False
                            pdf_url = ""

                        item_info[k]["item_pmids"].append({
                            "pmid": pmid,
                            "title": title,
                            "db_name": db_name,
                            "url": url,
                            "has_pdf": has_pdf,
                            "pdf_url": pdf_url
                        })

        item_info = associated_pmids.groupby("item_id")["pmid"].count().to_frame()
        item_info = item_info.rename(columns={"pmid": "counter"})
        item_info = item_info.to_dict("index")

        if add_pmids_for_each_item:
            item_to_pmids = associated_pmids.groupby("item_id")["pmid"].apply(list)
            add_item_pmids(item_to_pmids)

        return item_info

    def calculate_items_info(
        self,
        associated_pmids: pd.DataFrame,
        df: pd.DataFrame,
        item_type: str,
        add_pmids_for_each_item: bool=False
    ) -> Dict[str, Any]:
        """Creates an info dictionary containing information necessary for
        metrics calculation.

        Args:
            associated_pmids (pd.DataFrame): PMIDs of query.
            df (pd.DataFrame): Item DataFrame. Either drugs_df or targets_df.
            item_type (str): Type of the item ("target", "drug", etc.).
            add_pmids_for_each_item (bool): Add associated_pmids for each item under
                `item_pmids` field or not. Use `False` if you only need the counters.

        Returns:
            Dict[str, Any]: Counters and PMIDs for each of the items.

        """
        items_info = self._calculate_items_info(
            associated_pmids,
            add_pmids_for_each_item
        )
        # replace ID-like keys with actual names
        items_info = dict(zip(
            df.loc[items_info.keys(), "name"],
            items_info.values()
        ))

        return items_info

    def get_sentiment_for_item(self, item_info: Dict[str, Any]):
        pmids = [p["pmid"] for p in item_info["item_pmids"]]
        sentiments_df = self.db.get_sentiments(pmids)
        if len(sentiments_df) > 0:
            return sentiments_df["sentiment_score"].mean()
        else:
            return .0

    def get_metrics(
        self,
        query_pmids: List[str],
        items_info: Dict[str, Any],
        items_full_info: Dict[str, Any]
    ) -> Dict[str, List[Any]]:
        """Calculates metrics for each of the items based on `items_info`.

        Args:
            query_pmids (List[str]): PMIDs of query.
            items_info (Dict[str, Any]): Counters and PMIDs for each
                of the items intersecting with query.
            items_full_info (Dict[str, Any]): Counters and PMIDs for each
                of the possible items.

        Returns:
            Dict[str, List[Any]]: Updated with "metrics" key `items_info` dictionary.

        """
        for k, v in items_info.items():
            metrics = dict()

            metrics["(Search + {}) Publications"] = v["counter"]
            metrics["{} Publications"] = items_full_info[k]["counter"]

            TP = v["counter"]
            FP = items_full_info[k]["counter"] - v["counter"]
            FN = len(query_pmids) - v["counter"]

            metrics["Precision"] = TP / (TP + FP)
            metrics["Recall"] = TP / (TP + FN)

            beta = 0.5

            numenator = (1 + beta**2) * metrics["Precision"] * metrics["Recall"]
            denomenator = beta**2 * (metrics["Precision"] + metrics["Recall"])

            metrics[f"F-{beta}"] = numenator / denomenator

            metrics["sentiment"] = self.get_sentiment_for_item(v)

            metrics["ranking_score"] = (4 * metrics[f"F-{beta}"] + metrics["sentiment"]) / 5

            items_info[k]["metrics"] = metrics


        return items_info

    def items_to_df(self, items_info: Dict[str, List[Any]]) -> pd.DataFrame:
        """Converts `items_info` to DataFrame

        Args:
            items_info (Dict[str, List[Any]]): Counters and PMIDs for each
                of the items intersecting with query.

        Returns:
            pd.DataFrame: DataFrame with metrics as columns and items as indices.

        """
        metrics = dict([(k, v["metrics"]) for k, v in items_info.items()])
        df = pd.DataFrame.from_dict(metrics, orient="index")

        return df

    def resp_size_is_small_enough(
        self,
        resp: Dict[str, Any],
        limit_mb: int = 2.5
    ) -> bool:
        if (len(json.dumps(resp).encode()) / 2**20) > limit_mb:
            return False
        else:
            return True

    def filter_items(
        self,
        items_info: Dict[str, List[Any]],
        limit_results: int=50
    ) -> Dict[str, List[Any]]:
        """Filters out anomalies. By anomalies we understand items that have either low
        Precision or low Recall.

        Args:
            items_info (Dict[str, List[Any]]): Counters and PMIDs for each
                of the items intersecting with query.
            limit_results (int): Maximum results to return for each item.

        Returns:
            Dict[str, List[Any]]: Filtered Counters and PMIDs for each
                of the items intersecting with query.

        """

        df = self.items_to_df(items_info)

        if any([c not in df.columns for c in ["Precision", "Recall", "F-0.5"]]):
            return items_info

        p_quantile = df['Precision'].quantile(.90)
        r_quantile = df['Recall'].quantile(.90)

        filtered_df = df[(df["Precision"] > p_quantile)]
        # filtered_df = df.copy()
        filtered_df = filtered_df.nlargest(limit_results, "ranking_score")

        df_indices = filtered_df.index
        items_filtered = dict()
        for k in df_indices:
            items_filtered[k] = items_info[k]

        while not self.resp_size_is_small_enough(items_filtered):
            for k, v in items_filtered.items():
                articles = v["item_pmids"]
                articles = articles[:int(len(articles)//4)]
                items_filtered[k]["item_pmids"] = articles

        return items_filtered

    def hardcode(self, drugs_info: Dict[str, Any], query: str):
        hardcode_queries = [
            "covid",
            "omicron",
            "delta",
            "sars-cov",
            "corona"
        ]
        if any([q in query.lower() for q in hardcode_queries]):
            for drug, v in drugs_info.items():
                if drug in ["Favipiravir", "Ivermectin"]:
                    v["metrics"]["ranking_score"] = 1.0

        return drugs_info

    # @profile
    def search(
        self,
        query: str,
        do_filter: bool=True,
        add_pmids_for_each_item: bool=False,
        limit_results: int=50
    ) -> Dict[str, Any]:
        """Perform drugs and targets ranking with respect to query.

        Args:
            query (str): Query. It could be an illness, drug, group of drugs, etc.
            do_filter (bool): Apply filtering to get rid of anomalies. If applied,
                length of items will be significantly lower.
            add_pmids_for_each_item (bool): Add associated_pmids for each item under
                `item_pmids` field or not. Use `False` if you only need the counters.
            limit_results (int): Maximum results to return for each item.

        Returns:
            Dict[str, Any]: Ranking results.

        """
        # popular_df = get_popular_query(query, self.conn_item)
        # if len(popular_df) > 0:
        #     query_pmids = json.loads(popular_df.iloc[0].pmids)
        # else:
        query_pmids = query_all_resources(query)

        if len(query_pmids) == 0:
            return {
                "drugs": dict(),
                "targets": dict()
            }

        associated_pmids = self.db.get_pmids_for_items(query_pmids)

        drugs_info = self.calculate_items_info(
            associated_pmids[associated_pmids["item_type"] == "drug"],
            self.drugs_df,
            "drug",
            add_pmids_for_each_item
        )

        drugs_info = self.get_metrics(
            query_pmids,
            drugs_info,
            self.drugs_full_info
        )

        targets_info = self.calculate_items_info(
            associated_pmids[associated_pmids["item_type"] == "target"],
            self.targets_df,
            "target",
            add_pmids_for_each_item
        )

        targets_info = self.get_metrics(
            query_pmids,
            targets_info,
            self.targets_full_info
        )

        del associated_pmids

        drugs_info = self.hardcode(drugs_info, query)

        if do_filter:
            drugs_info = self.filter_items(drugs_info, limit_results)
            targets_info = self.filter_items(targets_info, limit_results)


        return {
            "drugs": drugs_info,
            "targets": targets_info
        }

