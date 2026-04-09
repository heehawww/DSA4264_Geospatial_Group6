# Primary School Scraper

This directory contains the Scrapy project used to collect MOE primary school registration and balloting data.

The nesting is normal for a Scrapy project:

- the outer `primary_school_scrape/` directory is the project root that holds `scrapy.cfg`
- the inner `primary_school_scrape/` directory is the Python package that Scrapy imports from

This is the same pattern as many Python tools that keep project files at the top level and importable code in a package folder underneath.

## Structure

- `scrapy.cfg`: Scrapy project entrypoint
- `primary_school_scrape/`: Scrapy source package
- `primary_school_scrape/spiders/primary.py`: main spider
- `schools.csv`: generated scraper output file (not intended to be committed)

## Output

The current spider exports its CSV output to:

- `schools.csv`

This file is treated as a generated artifact and should not be committed.

## Running

From the repository root:

```powershell
cd primary_school_scrape
scrapy crawl schools
```

If Playwright is required by the target page, make sure the project environment includes the necessary Playwright dependencies and browser install.
