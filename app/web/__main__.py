"""
Launches the OptionLab web GUI: python -m app.web
"""

import uvicorn


def main():

    uvicorn.run("app.web.server:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":

    main()
