import requests
from bs4 import BeautifulSoup  

def get_url(url):
    r = requests.get(url)
    return r.content


if __name__ == "__main__":
    c = get_url("https://www.reddit.com/r/Calculatedasshattery/")
    soup = BeautifulSoup(c, "html.parser")
    main = soup.find("div", class_="main-container")
    print(main.find_all("faceplate-partial"))
