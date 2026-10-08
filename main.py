import os
from dotenv import load_dotenv

def main():
    load_dotenv()

    print(".env test: " + os.getenv("TEST"))

if __name__ == "__main__":
    main()