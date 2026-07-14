from __future__ import annotations

import argparse
import json

from .manager import KnowledgeBaseManager
from .settings import KnowledgeBaseSettings


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage namespace-isolated knowledge bases")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list knowledge bases in the configured namespace")
    documents = subparsers.add_parser("documents-dir", help="create and print a knowledge base documents directory")
    documents.add_argument("name")
    ingest = subparsers.add_parser("ingest", help="ingest documents for a knowledge base")
    ingest.add_argument("name")
    ingest.add_argument("--rebuild", action="store_true")
    retrieve = subparsers.add_parser("retrieve", help="retrieve evidence without generating an answer")
    retrieve.add_argument("name")
    retrieve.add_argument("query")
    retrieve.add_argument("--top-k", type=int)
    args = parser.parse_args()

    settings = KnowledgeBaseSettings()
    manager = KnowledgeBaseManager(settings.namespace, settings=settings)
    if args.command == "list":
        print(json.dumps([item.model_dump() for item in manager.list_knowledge_bases()], ensure_ascii=False, indent=2))
    elif args.command == "documents-dir":
        print(manager.documents_dir(args.name))
    elif args.command == "ingest":
        print(manager.ingest(args.name, rebuild=args.rebuild).model_dump_json(indent=2))
    else:
        print(manager.retrieve(args.name, args.query, top_k=args.top_k).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
