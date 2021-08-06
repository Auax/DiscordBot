from difflib import SequenceMatcher
from typing import Union, Optional

import requests
from bs4 import BeautifulSoup

from misc import auth


class GeniusSong:
    def __init__(self, song, artist=None):
        """This class lets you get info of a song using the Genius API.
        """
        # Auth
        self.genius_token = auth.authenticate("config/authentication.json", "apis").get("genius_token")
        self.headers = {'Authorization': 'Bearer ' + self.genius_token}
        # Base url
        self.base_url = "http://api.genius.com"

        self.song = song
        self.artist = artist
        self.song_url = None
        self.song_hit = None
        self.lyrics = None

    def __str__(self):
        return self.song

    def get_response(self) -> Union[dict, bool]:
        # Get lyrics using the GENIUS API
        # Create endpoint URL
        search_url = self.base_url + "/search"
        # Query string
        querystring = {'q': self.song}
        response = requests.request("GET", search_url, headers=self.headers, params=querystring)
        if response.status_code == 200:
            return response.json()
        else:
            return False

    def filter_hit_by_artist(self, response: dict, min_similarity: float = 0.7) -> Union[dict, bool]:
        """Filter hits by an artist.
        If there is some error or the similarity is not met, then return False.
        :response: the dictionary containing all the hits
        :min_similarity: the min relationship between the found artist on the hit and the artist of YouTube.
        """
        try:
            for hit in response["response"]["hits"]:
                name = hit["result"]["primary_artist"]["name"]
                # Find the similarity between strings
                string_similarity = SequenceMatcher(None, name.lower(), self.artist.lower()).ratio()

                # Print info
                print("\n{:<12}{:<30}{:<30}".format("Score", "YouTube Artist", "Genius Artist"))
                print("{:<12.2f}{:<30}{:<30}".format(string_similarity, name, self.artist))

                if string_similarity > min_similarity:
                    self.song_hit = hit
                    self.song_url = hit["result"]["url"]
                    return hit
                else:
                    return False

        except KeyError:
            return False

    def get_lyrics(self, song_url: Optional[str] = None) -> Union[str, bool]:
        """Use web scrapping to get the lyrics from the Genius website.
        :song_api_path: the required path (returned by the Genius API)
        to find the website containing the lyrics
        """

        if not self.song_url and not song_url:
            return False

        song_url = song_url if song_url else self.song_url
        page = requests.get(song_url)
        html = BeautifulSoup(page.text, "html.parser")
        # Remove script tags that they put in the middle of the lyrics
        [h.extract() for h in html('script')]
        # At least Genius is nice and has a tag called 'lyrics'!
        try:
            lyrics = html.find("div", class_="lyrics").get_text()  # Updated css where the lyrics are based in HTML
            return lyrics

        except AttributeError:
            return False

    @staticmethod
    def split_lyrics(lyrics: str) -> list[dict[str, str]]:
        """Split a text (can include paragraphs) to chunks.
        lyrics: the raw lyrics text
        """
        paragraphs = lyrics.split("\n\n")
        chunk_size = 1024
        escape = "\n\n"

        fields = []
        blank_char = "​"  # U+200B ​ (used for empty title)
        for paragraph in paragraphs:
            if len(paragraph) <= chunk_size:
                if paragraph:
                    fields.append(
                        {"name": blank_char, "value": paragraph + escape})
            else:
                current_line = ""
                lines = paragraph.splitlines()
                for line in lines:
                    if len(line) + len(current_line) <= chunk_size:
                        current_line += line + "\n"
                        if lines.index(line) == len(lines) - 1:
                            fields.append({"name": blank_char, "value": current_line})
                    else:
                        fields.append({"name": blank_char, "value": current_line})
                        current_line = line + "\n"

        return fields
