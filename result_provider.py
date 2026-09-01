import re
import hashlib
import httpx
from bs4 import BeautifulSoup

class ProviderError(Exception): pass
class ResultNotAvailable(Exception): pass
class CaptchaRequired(Exception): pass

class BiseGujranwalaProvider:
    """
    Official-site adapter.

    BISE Gujranwala currently exposes a CAPTCHA on its public result page.
    This adapter deliberately detects that condition instead of bypassing it.
    If BISE changes its public endpoint/form, update OFFICIAL_RESULT_URL and,
    if necessary, the form field mapping below.
    """

    def __init__(self, url, timeout=20):
        self.url = url
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; BISE-GRW-Result-Bot/1.0)",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def fetch(self, roll_number, class_name, year):
        roll_number = str(roll_number).strip()
        if not re.fullmatch(r"\d{3,10}", roll_number):
            raise ProviderError("Invalid roll number format.")

        async with httpx.AsyncClient(follow_redirects=True, timeout=self.timeout, headers=self.headers) as client:
            try:
                response = await client.get(self.url)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise ProviderError(f"HTTP request failed: {e}") from e

            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True).lower()

            if "captcha" in text or "enter the captcha" in text:
                raise CaptchaRequired()

            # Generic extraction for simple result pages.
            # Exact BISE result fields can be added here if the board changes
            # the endpoint to a public, non-CAPTCHA result form.
            if roll_number not in html and "result" not in text:
                raise ResultNotAvailable()

            return self._parse_generic(soup, roll_number, class_name, year)

    def _parse_generic(self, soup, roll_number, class_name, year):
        data = {
            "roll_number": roll_number,
            "class_name": class_name,
            "year": int(year),
            "name": None,
            "status": "RESULT AVAILABLE",
            "total_marks": None,
            "max_marks": None,
            "percentage": None,
            "subjects": {},
            "source": self.url,
        }

        # Parse tables with rows such as Subject | Marks.
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) >= 2:
                    key = cells[0].lower()
                    value = cells[1]
                    if "name" == key:
                        data["name"] = value
                    elif "status" in key:
                        data["status"] = value
                    elif "total" in key and "mark" in key:
                        data["total_marks"] = self._number(value)
                    elif "percent" in key:
                        data["percentage"] = self._number(value)

        if data["percentage"] is None and data["total_marks"] and data["max_marks"]:
            data["percentage"] = round(data["total_marks"] / data["max_marks"] * 100, 2)

        if not data["name"] and not data["total_marks"] and not data["subjects"]:
            raise ResultNotAvailable()

        raw = repr(data).encode()
        data["result_hash"] = hashlib.sha256(raw).hexdigest()
        return data

    @staticmethod
    def _number(value):
        m = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
        return float(m.group()) if m else None
