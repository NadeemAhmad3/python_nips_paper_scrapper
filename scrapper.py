import aiohttp
import asyncio
import os
import json
import re
from aiofiles import open as aio_open
from bs4 import BeautifulSoup

# Constants
BASE_URL = "https://papers.nips.cc/"
DOWNLOAD_PATH = "D:/ds"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
]

# Helper Functions
def sanitize_filename(filename):
    return re.sub(r'[\\/:*?"<>|]', '_', filename)

def extract_bib_field(bib_text, field_name):
    pattern = re.compile(fr'{field_name}\s*=\s*{{([^{{}}]+)}}')
    matches = pattern.findall(bib_text)
    return matches[-1].strip() if matches else None

def extract_pdf_url(bib_text):
    pattern = re.compile(r'url\s*=\s*{(https?://[^"]+\.pdf)}')
    match = pattern.search(bib_text)
    return match.group(1) if match else None

def extract_all_bib_fields(bib_text):
    fields = {}
    # Extract all fields from the .bib entry
    pattern = re.compile(r'(\w+)\s*=\s*{([^{}]+)}')
    matches = pattern.findall(bib_text)
    for key, value in matches:
        fields[key] = value.strip()
    return fields

# Main Scraping Logic
async def fetch(session, url):
    headers = {"User-Agent": USER_AGENTS[0]}  # Randomize if needed
    async with session.get(url, headers=headers) as response:
        return await response.text()

async def download_pdf(session, url, file_path):
    async with session.get(url) as response:
        async with aio_open(file_path, "wb") as f:
            await f.write(await response.read())

async def process_abstract(session, url, folder_path, folder_name):
    try:
        html = await fetch(session, url)
        soup = BeautifulSoup(html, "html.parser")
        pdf_link = soup.select_one("a.btn.btn-light.btn-spacer")
        if pdf_link:
            pdf_url = BASE_URL + pdf_link["href"]
            await process_bib_and_pdf(session, pdf_url, folder_path, folder_name)
    except Exception as e:
        print(f"Error processing abstract: {url} | {e}")

async def process_bib_and_pdf(session, bib_url, folder_path, folder_name):
    try:
        bib_text = await fetch(session, bib_url)
        pdf_url = extract_pdf_url(bib_text)
        if pdf_url:
            # Extract all fields from the .bib file
            bib_fields = extract_all_bib_fields(bib_text)

            # Sanitize the title, booktitle, and author for file naming
            title = bib_fields.get("title", "Unknown_Title")
            booktitle = bib_fields.get("booktitle", "Unknown_Booktitle")
            author = bib_fields.get("author", "Unknown_Author")

            sanitized_title = sanitize_filename(title)
            sanitized_booktitle = sanitize_filename(booktitle)
            sanitized_author = sanitize_filename(author)

            # Create PDF and JSON folder paths
            pdf_folder_path = os.path.join(folder_path, "pdf")
            json_folder_path = os.path.join(folder_path, f"json_{folder_name}")  # Updated to include folder_name

            # Ensure the folders exist
            os.makedirs(pdf_folder_path, exist_ok=True)
            os.makedirs(json_folder_path, exist_ok=True)

            # Create the PDF filename using the title
            pdf_file_name = f"{sanitized_booktitle}_{sanitized_author}.pdf"
            pdf_file_path = os.path.join(pdf_folder_path, pdf_file_name)

            # Download PDF
            await download_pdf(session, pdf_url, pdf_file_path)
            print(f"Downloaded PDF: {pdf_file_path}")

            # Save all .bib data to JSON
            bib_data = bib_fields  # Include all extracted fields
            bib_data["url"] = pdf_url  # Add the PDF URL to the JSON data

            json_file_name = f"{sanitized_title}.json"  # Use the same title as the .bib file
            json_file_path = os.path.join(json_folder_path, json_file_name)
            async with aio_open(json_file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(bib_data, indent=4))
            print(f"Saved JSON: {json_file_path}")
    except Exception as e:
        print(f"Error processing bib and PDF: {bib_url} | {e}")

async def process_href(session, url, folder_path, folder_name):
    try:
        html = await fetch(session, url)
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("li > a")
        for link in links:
            href = link["href"]
            if href.startswith("/paper_files/paper/"):
                await process_abstract(session, BASE_URL + href, folder_path, folder_name)
    except Exception as e:
        print(f"Error processing href: {url} | {e}")

async def main():
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("li > a")
        tasks = []
        for link in links:
            href = link["href"]
            if href.startswith("/paper_files/paper/"):
                folder_name = href.replace("/paper_files/paper/", "")
                folder_path = os.path.join(DOWNLOAD_PATH, folder_name)
                os.makedirs(folder_path, exist_ok=True)
                tasks.append(process_href(session, BASE_URL + href, folder_path, folder_name))
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
