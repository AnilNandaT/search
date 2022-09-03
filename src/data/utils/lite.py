import os
import sys
if sys.path[0].endswith("/src/data/utils"):
    sys.path.append(sys.path[0].split("/src/data/utils")[0])
from typing import List
from time import time

import pandas as pd
import sqlite3
from sqlite3 import Error
from tqdm.auto import tqdm

from src.data.utils.processing import preprocess_query
from src.data.utils.io import load_json, load_pkl
from src.config import (
    ARTICLE_DATABASE
)

class DatabaseConnector:
    def __init__(self):
        self.conn = sqlite3.connect(ARTICLE_DATABASE)
        self.cursor = self.conn.cursor()

    def create_dbs(self):
        create_table = """
        CREATE TABLE IF NOT EXISTS article_titles (
            pmid text PRIMARY KEY UNIQUE,
            db_name text,
            url text,
            title text,
            pmcid text
        );
        """
        self.cursor.execute(create_table)

        create_table = """
        CREATE TABLE IF NOT EXISTS article_items (
            pmid text KEY,
            db_name text,
            item_id text,
            item_type text
        );
        """

        create_index = """
        CREATE INDEX IF NOT EXISTS article_items_index
        ON article_items(pmid);
        """

        self.cursor.execute(create_table)
        self.cursor.execute(create_index)

        create_table = """
        CREATE TABLE IF NOT EXISTS popular_queries (
            query text PRIMARY KEY,
            pmids text
        );
        """

        self.cursor.execute(create_table)

        create_table = """
        CREATE TABLE IF NOT EXISTS item_counter (
            item_id text PRIMARY KEY,
            item_type text,
            counter integer
        );
        """

        self.cursor.execute(create_table)

        create_table = """
        CREATE TABLE IF NOT EXISTS article_sentiments (
            pmid text PRIMARY KEY,
            sentiment_score REAL
        );
        """

        self.cursor.execute(create_table)

    def add_article_items(
        self,
        pmids: List[str],
        db_name: str,
        item_ids: List[str],
        item_types: List[str]
    ):
        for pmid, item_id, item_type in zip(pmids, item_ids, item_types):
            self.cursor.execute(
                'insert or replace into article_items '
                '(pmid, db_name, item_id, item_type) '
                'values (?,?,?,?);',
                (pmid, db_name, item_id, item_type)
            )
        self.conn.commit()


    def add_titles_info(
        self,
        pmids: List[str],
        db_name: str,
        urls: List[str],
        titles: List[str],
        pmcids: List[str]
    ):

        for pmid, url, title, pmcid in zip(pmids, urls, titles, pmcids):
            self.cursor.execute(
                'insert or replace into article_titles '
                '(pmid, db_name, url, title, pmcid) '
                'values (?,?,?,?,?);',
                (pmid, db_name, url, title, pmcid)
            )
        self.conn.commit()


    def add_popular_query(self, query: str, pmids_str: str):
        self.cursor.execute(
            'insert or replace into popular_queries '
            '(query, pmids) '
            'values (?,?);',
            (preprocess_query(query), pmids_str)
        )
        self.conn.commit()

    def add_counters(self):
        q = """
            SELECT
            item_id,
            item_type,
            COUNT(pmid) as counter
            FROM article_items
            GROUP BY item_id
            """

        counter_df = pd.read_sql_query(
            q,
            con=self.conn
        )

        counter_df["counter"] = counter_df["counter"].map(int)
        counter_df = counter_df.set_index("item_id")

        counter_df.to_sql(
            "item_counter",
            if_exists="replace",
            con=self.conn
        )

    def add_sentiments(self, pmids: List[str], sentiments: List[float]):
        for pmid, sentiment in zip(pmids, sentiments):
            self.cursor.execute(
                'insert or replace into article_sentiments '
                '(pmid, sentiment_score) '
                'values (?,?);',
                (pmid, sentiment)
            )

        self.conn.commit()

    def get_known_item_ids(self, db_name: str):
        db_where_str = f'AND db_name == "{db_name}"'
        df = pd.read_sql_query(
            f"""
            SELECT DISTINCT item_id FROM article_items
            WHERE 1=1
            {db_where_str if db_name != "" else ""}
            """,
            self.conn
        )
        df["item_id"] = df["item_id"].map(str)
        known = set(df.item_id.to_list())

        return known

    def get_unknown_info_pmids(self, db_name: str):
        db_where_str = f'AND db_name == "{db_name}"'
        df = pd.read_sql_query(
            f"""
            SELECT pmid FROM article_items
            WHERE pmid NOT IN (
                SELECT pmid FROM article_titles
            )
            {db_where_str if db_name != "" else ""}
            """,
            self.conn
        )
        df["pmid"] = df["pmid"].map(str)
        unknown = df.pmid.to_list()

        return unknown

    def get_unique_pmids(self, db_name: str):
        db_where_str = f'AND db_name == "{db_name}"'
        df = pd.read_sql_query(
            f"""
            SELECT DISTINCT pmid FROM article_items
            WHERE 1=1
            {db_where_str if db_name != "" else ""}
            """,
            self.conn
        )
        df["pmid"] = df["pmid"].map(str)
        known = list(set(df.pmid.to_list()))

        return known

    def get_titles(self, pmids: List[str]):
        where_str = f'WHERE pmid IN ("{", ".join(pmids)}")'
        for chunk in pd.read_sql_query(
            f"""
            SELECT pmid, db_name, url, title, pmcid FROM article_titles
            {where_str if len(pmids) > 0 else ""}
            """,
            self.conn,
            chunksize=10000
        ):
            yield chunk

    def drop_non_small(self):
        df = pd.read_csv("src/data/drugs.csv")
        useless_ids = df[(
            (df["type"] != "SmallMoleculeDrug") | (df["state"] != "solid")
        )]["drugbank_id"]
        SEP_q = '", "'
        delete = f"""
        DELETE FROM article_items
        WHERE item_id IN ("{SEP_q.join(useless_ids)}")
        """
        self.cursor.execute(delete)
        self.conn.commit()

    def get_pmids_for_items(
        self,
        query_pmids: List[str] = [],
        item_ids: List[str] = [],
        item_type: str = "",
    ):
        SEP_q = '", "'
        pmid_str = f'AND pmid IN ("{SEP_q.join(query_pmids)}")'
        items_str = f'AND item_id IN ("{SEP_q.join(item_ids)}")'
        item_type_str = f"AND item_type = '{item_type}'"

        return pd.read_sql_query(
            f"""
            SELECT pmid, db_name, item_id, item_type FROM article_items
            WHERE 1=1
            {pmid_str if len(query_pmids) > 0 else ""}
            {items_str if len(item_ids) > 0 else ""}
            {item_type_str if item_type != "" else ""}
            """,
            self.conn
        )

    def get_popular_query(self, query: str, conn):
        return pd.read_sql_query(
        f"""
        SELECT pmids FROM popular_queries
        WHERE query = "{preprocess_query(query)}"
        """, self.conn)

    def get_counters(self):
        return pd.read_sql_query(
            f"""
            SELECT item_id, item_type, counter FROM item_counter
            """,
            self.conn
        )

    def get_sentiments(self, pmids: List[str]):
        SEP_q = '", "'
        pmid_str = f'AND pmid IN ("{SEP_q.join(pmids)}")'
        df = pd.read_sql_query(
            f"""
            SELECT pmid, sentiment_score FROM article_sentiments
            WHERE 1=1
            {pmid_str if len(pmids) > 0 else ""}
            """,
            self.conn
        )

        return df

    def selectall_from_table(self, tablename):
        return pd.read_sql_query(
            f"""
            SELECT * FROM {tablename}
            """,
            self.conn
        )

    def vacuum(self):
        self.cursor.execute("VACUUM;")
        self.conn.commit()

if __name__ == '__main__':
    db = DatabaseConnector()
    # db.cursor.execute("""
    # DROP TABLE IF EXISTS article_sentiments
    # """)
    # db.conn.commit()
    db.create_dbs()
    # db.drop_non_small()
    db.add_counters()
    # db.vacuum()
    # print(len(db.get_unique_pmids("PubMed")))
    print(db.selectall_from_table("article_sentiments"))
