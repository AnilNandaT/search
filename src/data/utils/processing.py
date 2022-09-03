import re
punctuation = """!"#$%&'*+,./:;<=>?@[\]^_`{|}~"""
def preprocess_query(query):
    query = query.lower()
    # print(punctuation)
    # punctuation = punctuation.replace("-", "")
    query = query.translate(str.maketrans(punctuation, ' ' * len(punctuation)))

    query = query.strip()
    query = re.sub('[ ]+', ' ', query)

    return query
