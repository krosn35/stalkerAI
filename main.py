import os
from dotenv import load_dotenv

import api
import gui

def main():
    load_dotenv()
    print(".env test: " + os.getenv("TEST"))

    api.init()

    gui.App().mainloop()

if __name__ == "__main__":
    main()