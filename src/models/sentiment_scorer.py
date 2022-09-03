import pandas as pd
import os
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from tqdm.auto import tqdm

tqdm.pandas()

from textblob import TextBlob

words_remove = ["ax","i","you","edu","s","t","m","subject","can","lines","re","what", "there","all","we",
                "one","the","a","an","of","or","in","for","by","on","but","is","in","a","not","with","as",
                "was","if","they","are","this","and","it","have","has","from","at","my","be","by","not","that","to",
                "from","com","org","like","likes","so","said","from","what","told","over","more","other",
                "have","last","with","this","that","such","when","been","says","will","also","where","why",
                "would","today", "in", "on", "you", "r", "d", "u", "hw","wat", "oly", "s", "b", "ht",
                "rt", "p","the","th", "n", "was", "the", "via"]


class SentimentScorer:
    def __init__(self, df):
        self.df = df

    def cleantext(self, words_to_remove=words_remove):
        # convert tweets to lowercase
        self.df['Text'] = self.df['Text'].str.lower()

        #remove user mentions
        self.df['Text'] = self.df['Text'].replace(r'^(@\w+)',"", regex=True)

        #remove 'rt' in the beginning
        self.df['Text'] = self.df['Text'].replace(r'^(rt @)',"", regex=True)

        #remove_symbols
        self.df['Text'] = self.df['Text'].replace(r'[^a-zA-Z0-9]', " ", regex=True)

        #remove punctuations
        self.df['Text'] = self.df['Text'].replace(r'[[]!"#$%\'()\*+,-./:;<=>?^_`{|}]+',"", regex = True)

        #remove_URL(x):
        self.df['Text'] = self.df['Text'].replace(r'https.*$', "", regex = True)

        #remove 'amp' in the text
        self.df['Text'] = self.df['Text'].replace(r'amp',"", regex = True)

        #remove words of length 1 or 2
        self.df['Text'] = self.df['Text'].replace(r'\b[a-zA-Z]{1,2,3,4}\b','', regex=True)

        #remove extra spaces in the tweet
        self.df['Text'] = self.df['Text'].replace(r'^\s+|\s+$'," ", regex=True)

        #remove numbers in the tweet
        #df['Text'] = df['Text'].replace(r'[0-9]'," ", regex=True)

        #remove stopwords and words_to_remove
        stop_words = set(stopwords.words('english'))

        self.df['fully_cleaned'] = self.df['Text'].progress_apply(
            lambda x: ' '.join(
                [word for word in x.split() if word not in stop_words]
            )
        )


    def preprocess(self):
        # self.df = self.df[['title', 'doi', 'abstract']]
        self.df.rename(columns = {'abstract':'Text'}, inplace = True)
        self.df['Text'] = self.df['Text'].fillna("")

        self.cleantext(self.df)

    def get_scores(self):
        self.preprocess()

        self.df['sentiment'] = self.df['fully_cleaned'].progress_apply(
            lambda x: TextBlob(x).sentiment.polarity
        )

        return self.df['sentiment']
