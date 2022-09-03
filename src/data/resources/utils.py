import asyncio
import aiohttp
import sys
if sys.path[0].endswith("/src/data/resources"):
    sys.path.append(sys.path[0].split("/src/data/resources")[0])

from src.data.resources.pubmed_resource import PubMedResource
from src.data.resources.crossref_resource import CrossrefResource
from src.data.resources.xrxiv_resource import XrxivResource


LIST_OF_RESOURCES = [
    PubMedResource(),
    XrxivResource()
]

async def send_query(resource, query):
    return resource.get_ids_by_query(query)

async def send_requests(query):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for resource in LIST_OF_RESOURCES:
            tasks.append(send_query(resource, query))
        ids_list = await asyncio.gather(*tasks)

    ids = []
    for ids_l in ids_list:
        ids += ids_l

    return ids

def query_all_resources(query):
    loop = asyncio.get_event_loop()
    ids = loop.run_until_complete(send_requests(query))

    return list(set(ids))

if __name__ == '__main__':
    ids = query_all_resources('molnupiravir omicron')
    print(len(ids))
