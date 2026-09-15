"""
Resolves an ambiguous place or brand name (e.g. "McDonald's") to the
nearest real candidates near a reference point, instead of trusting
the first geocoding match — which can be a wrong, differently-named
building entirely (see DEVELOPMENT.md's "macdonal" -> Macdonald House
incident).
"""

import argparse
import json

from onemap import search_location, search_places, OneMapError, onemap_error_reason


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--query",
        required=True,
        help="Place or brand name to search for, e.g. \"McDonald's\".",
    )
    parser.add_argument(
        "--near",
        required=True,
        help="Address or place to measure distance from.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum number of candidates to return.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result (or any failure) as JSON instead of text.",
    )
    args = parser.parse_args()

    def emit_error(reason: str, message: str, **extra) -> None:
        if args.json:
            print(json.dumps({"error": reason, "message": message, **extra}))
        else:
            print(message)

    try:
        near = search_location(args.near)
    except ValueError as error:
        emit_error("near_not_found", str(error))
        return
    except OneMapError as error:
        emit_error(onemap_error_reason(error), str(error))
        return

    try:
        candidates = search_places(args.query, near, limit=args.limit)
    except ValueError as error:
        emit_error("place_not_found", str(error))
        return
    except OneMapError as error:
        emit_error(onemap_error_reason(error), str(error))
        return

    result = {
        "query": args.query,
        "near": args.near,
        "candidates": candidates,
    }

    if args.json:
        print(json.dumps(result))
    else:
        print()
        print(f"Nearest matches for '{args.query}' near {args.near}:")
        for candidate in candidates:
            print(f"- {candidate['name']} ({candidate['distance_km']} km)")


if __name__ == "__main__":
    main()
