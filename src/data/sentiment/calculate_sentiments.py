import os
import sys
if sys.path[0].endswith("/src/data/sentiment"):
    sys.path.append(sys.path[0].split("/src/data/sentiment")[0])

import pandas as pd

from src.data.utils.lite import DatabaseConnector
from src.models.sentiment_scorer import SentimentScorer
from src.config import SERVER_DUMPS_PATH

if __name__ == '__main__':
    db = DatabaseConnector()
    dumps_path = SERVER_DUMPS_PATH
    for dump in os.listdir(dumps_path):
        df = pd.read_json(os.path.join(dumps_path, dump), lines=True)
        ss = SentimentScorer(df)

        scores = ss.get_scores()

        db.add_sentiments(df["doi"], scores)
