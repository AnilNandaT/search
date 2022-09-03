import sys
if sys.path[0].endswith("/src/data/resources"):
    sys.path.append(sys.path[0].split("/src/data/resources")[0])
from argparse import ArgumentParser

from src.data.resources.pubmed_resource import PubMedResource
from src.data.resources.crossref_resource import CrossrefResource
from src.data.resources.xrxiv_resource import XrxivResource

resource_name_map = {
    "pubmed": PubMedResource(),
    "crossref": CrossrefResource(),
    "xrxiv": XrxivResource()
}

if __name__ == '__main__':
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser')

    for k in resource_name_map:
        _ = subparsers.add_parser(k)

    for name, p in subparsers.choices.items():
        p.add_argument(
            "--items",
            action="store_true",
            help="Query all possible items and get ids of articles."
        )

        p.add_argument(
            "--info",
            action="store_true",
            help="Get articles' info."
        )

        p.add_argument(
            "--dump",
            action="store_true",
            help="Get articles dump."
        )
    args = parser.parse_args()

    if args.subparser in resource_name_map:
        if args.items:
            while True:
                try:
                    print("Items collection started!")
                    resource_name_map[args.subparser].insert_ids_items()
                    print("Items collection finished!")
                    break
                except Exception as e:
                    print(repr(e))
                    continue
        if args.info:
            print("Info collection started!")
            resource_name_map[args.subparser].insert_article_info()
            print("Info collection finished!")

        if args.dump:
            print("Dumping started!")
            resource_name_map[args.subparser].get_dump()
            print("Dumping finished!")
