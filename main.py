import os
from dotenv import load_dotenv

import api
from agent import check_candidate

def main():
    load_dotenv()
    print(".env test: " + os.getenv("TEST"))
    api.init()

    info = input("Údaje o kandidátovi: ")
    report = check_candidate(info)
    print(report.model_dump_json(indent=2))

if __name__ == "__main__":
    main()