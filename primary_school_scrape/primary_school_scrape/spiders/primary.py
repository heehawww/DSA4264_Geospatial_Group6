# import scrapy


# class SchoolItem(scrapy.Item):
#     Name = scrapy.Field()
#     Vacancies = scrapy.Field()
#     Phase_1 = scrapy.Field()
#     Phase_1_notes = scrapy.Field()
#     Phase_2A = scrapy.Field()
#     Phase_2A_Ratio = scrapy.Field()
#     Phase_2A_Balloting = scrapy.Field()
#     Phase_2A_Balloting_ratio = scrapy.Field()    
#     Phase_2B = scrapy.Field()
#     Phase_2B_ratio = scrapy.Field()
#     Phase_2B_Balloting = scrapy.Field()
#     Phase_2B_Balloting_ratio = scrapy.Field()
#     Phase_2C = scrapy.Field()
#     Phase_2C_ratio = scrapy.Field()
#     Phase_2C_Balloting = scrapy.Field()
#     Phase_2C_Balloting_ratio = scrapy.Field()
#     Phase_2C_sup = scrapy.Field()
#     Phase_2C_sup_ratio = scrapy.Field()
#     Phase_2C_sup_Balloting = scrapy.Field()
#     Phase_2C_sup_Balloting_ratio = scrapy.Field()
# class ballotSpider(scrapy.Spider):
#     name = "schools"
#     allowed_domains = ["https://www.moe.gov.sg/primary/p1-registration/past-vacancies-and-balloting-data"]
#     start_urls = ['https://www.moe.gov.sg/primary/p1-registration/past-vacancies-and-balloting-datay']

#     custom_settings = {
#         'FEEDS': {
#             'players.csv': {
#                 'format': 'csv',
#                 'item_classes': [SchoolItem],
#                 'overwrite': True,
#                 'fields': [
#                     'Name',
#                     'Vacancies',
#                     'Phase_1',
#                     'Phase_1_notes',
#                     'Phase_2A',
#                     'Phase_2A_Ratio',
#                     'Phase_2A_Balloting',
#                     'Phase_2A_Balloting_ratio',
#                     'Phase_2B',
#                     'Phase_2B_Ratio',
#                     'Phase_2B_Balloting',
#                     'Phase_2B_Balloting_ratio',
#                     'Phase_2C',
#                     'Phase_2C_Ratio',
#                     'Phase_2C_Balloting',
#                     'Phase_2C_Balloting_ratio',
#                     'Phase_2C_sup',
#                     'Phase_2C_sup_ratio',
#                     'Phase_2C_sup_Balloting',
#                     'Phase_2C_sup_Balloting_ratio'
#                 ]
#             },
#         }
#     }

#     def checker(self,text):
#         if text == "All eligible applicants were offered a place.":
#             results = "All applicants were successful"
#         elif text == "Balloting was not conducted as the number of applicants was less than or equal to the number of vacancies.":
#             results = "There were more applicants than vacancies" 
#         else:
#             results = "No registration was conducted"
#         return results
    
#     def parse(self, response):
#         table = response.xpath("//div[@class='moe-vacancies-ballot-app'][1]")
#         for row in table.xpath('/div[0]'):
#             name = row.xpath('./div/h3/text()').get()
#             info = row.xpath('./div[1]')
#             yield SchoolItem(
#                 Name=name,
#                 Vacancies=info.xpath('./div[0]//div[contains(@class"moe-vacancies-ballot-card")]/p/text()').get(),
#                 Phase_1=self.checker(info.xpath('./div[1]/h4').get_attribute("class")),
#                 Phase_1_notes=info.xpath('./div[1]//p/text()').get(),
#                 Phase_2A=self.checker(info.xpath('./div[2]/p[1]/text()').get()),
#                 Phase_2A_Ratio=info.xpath('./div[2]/div/div/p[2]/text()').get() + "/" + info.xpath('./div[2]/div/div[1]/p[2]/text()').get(),
#                 Phase_2A_Balloting=info.xpath('./div[2]/div[1]//i/text()').get(),
#                 Phase_2A_Balloting_ratio=lambda x: info.xpath('./div[2]/div[3]/p[1]/text()').get() + "/" + info.xpath('./div[2]/div[3]/p[2]/text()').get() if x == "Yes" else "N/A",
#                 Phase_2B=self.checker(info.xpath('./div[3]/p[1]/text()').get()),
#                 Phase_2B_Ratio=info.xpath('./div[3]/div/div/p[2]/text()').get() + "/" + info.xpath('./div[3]/div/div[1]/p[2]/text()').get(),
#                 Phase_2B_Balloting=info.xpath('./div[3]/div[1]//i/text()').get(),
#                 Phase_2B_Balloting_ratio=lambda x: info.xpath('./div[3]/div[3]/p[1]/text()').get() + "/" + info.xpath('./div[3]/div[3]/p[2]/text()').get() if x == "Yes" else "N/A",
#                 Phase_2C=self.checker(info.xpath('./div[4]/p[1]/text()').get()),
#                 Phase_2C_Ratio=info.xpath('./div[4]/div/div/p[2]/text()').get() + "/" + info.xpath('./div[4]/div/div[1]/p[2]/text()').get(),
#                 Phase_2C_Balloting=info.xpath('./div[4]/div[1]//i/text()').get(),
#                 Phase_2C_Balloting_ratio=lambda x: info.xpath('./div[4]/div[3]/p[1]/text()').get() + "/" + info.xpath('./div[4]/div[3]/p[2]/text()').get() if x == "Yes" else "N/A",
#                 Phase_2C_sup=info.xpath('./div[5]/p[1]/text()').get(),
#                 Phase_2C_sup_ratio=lambda x: info.xpath('./div[5]/p[4]/text()').get() if x != "No registration in Phase 2C Supplementary was conducted as all vacancies were filled by Phase 2C." else "N/A",
#                 Phase_2C_sup_Balloting=info.xpath('./div[5]/div[1]//i/text()').get(),
#                 Phase_2C_sup_Balloting_ratio=lambda x: info.xpath('./div[5]/div[3]/p[1]/text()').get() + "/" + info.xpath('./div[5]/div[3]/p[2]/text()').get() if x == "Yes" else "N/A"
#             )


# import scrapy


# class SchoolItem(scrapy.Item):
#     Name = scrapy.Field()
#     Vacancies = scrapy.Field()
#     Phase_1 = scrapy.Field()
#     Phase_1_notes = scrapy.Field()
#     Phase_2A = scrapy.Field()
#     Phase_2A_Ratio = scrapy.Field()
#     Phase_2A_Balloting = scrapy.Field()
#     Phase_2A_Balloting_ratio = scrapy.Field()
#     Phase_2B = scrapy.Field()
#     Phase_2B_ratio = scrapy.Field()
#     Phase_2B_Balloting = scrapy.Field()
#     Phase_2B_Balloting_ratio = scrapy.Field()
#     Phase_2C = scrapy.Field()
#     Phase_2C_ratio = scrapy.Field()
#     Phase_2C_Balloting = scrapy.Field()
#     Phase_2C_Balloting_ratio = scrapy.Field()
#     Phase_2C_sup = scrapy.Field()
#     Phase_2C_sup_ratio = scrapy.Field()
#     Phase_2C_sup_Balloting = scrapy.Field()
#     Phase_2C_sup_Balloting_ratio = scrapy.Field()


# class ballotSpider(scrapy.Spider):
#     name = "schools"

#     # FIX 1: allowed_domains must be just the domain, not a full URL
#     allowed_domains = ["www.moe.gov.sg"]

#     # FIX 2: Removed the typo "datay" → "data"
#     start_urls = ["https://www.moe.gov.sg/primary/p1-registration/past-vacancies-and-balloting-data"]

#     custom_settings = {
#         "FEEDS": {
#             "schools.csv": {
#                 "format": "csv",
#                 "item_classes": [SchoolItem],
#                 "overwrite": True,
#                 "fields": [
#                     "Name",
#                     "Vacancies",
#                     "Phase_1",
#                     "Phase_1_notes",
#                     "Phase_2A",
#                     "Phase_2A_Ratio",
#                     "Phase_2A_Balloting",
#                     "Phase_2A_Balloting_ratio",
#                     "Phase_2B",
#                     "Phase_2B_ratio",
#                     "Phase_2B_Balloting",
#                     "Phase_2B_Balloting_ratio",
#                     "Phase_2C",
#                     "Phase_2C_ratio",
#                     "Phase_2C_Balloting",
#                     "Phase_2C_Balloting_ratio",
#                     "Phase_2C_sup",
#                     "Phase_2C_sup_ratio",
#                     "Phase_2C_sup_Balloting",
#                     "Phase_2C_sup_Balloting_ratio",
#                 ],
#             }
#         },
#         # Polite crawling
#         "DOWNLOAD_DELAY": 1.5,
#         "ROBOTSTXT_OBEY": True,
#         "USER_AGENT": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) "
#             "Chrome/120.0.0.0 Safari/537.36"
#         ),
#     }

#     def checker(self, text):
#         """
#         FIX 3: Original logic had the two non-None branches swapped.
#         Maps MOE's verbose status text to a short readable label.
#         """
#         if text is None:
#             return "N/A"
#         if "All eligible applicants were offered a place" in text:
#             return "All applicants were successful"
#         if "Balloting was not conducted" in text:
#             # FIX 3: original incorrectly labelled this as "more applicants than vacancies"
#             return "No balloting needed – vacancies not exceeded"
#         if "No registration" in text:
#             return "No registration was conducted"
#         # Return raw text for any unrecognised message so no data is lost
#         return text.strip()

#     def safe_ratio(self, numerator, denominator):
#         """Return 'num/den' or 'N/A' if either value is missing."""
#         if numerator and denominator:
#             return f"{numerator.strip()}/{denominator.strip()}"
#         return "N/A"

#     def parse(self, response):
#         # FIX 4: XPath uses 1-based indexing, not 0-based.
#         # The top-level wrapper holds one card per school.
#         school_cards = response.xpath("//div[contains(@class,'moe-vacancies-ballot-app')]//div[contains(@class,'moe-vacancies-ballot-card')]")

#         if not school_cards:
#             self.logger.warning(
#                 "No school cards found. The page may require JavaScript rendering. "
#                 "Consider enabling Playwright or Splash middleware."
#             )
#             return

#         for card in school_cards:
#             # ── School name ───────────────────────────────────────────────────
#             name = card.xpath(".//h3/text()").get("").strip()

#             # ── Total vacancies ───────────────────────────────────────────────
#             vacancies = card.xpath(
#                 ".//div[contains(@class,'total-vacancies')]//p/text()"
#             ).get("").strip()

#             # ── Phase 1 ───────────────────────────────────────────────────────
#             phase1_div = card.xpath(".//div[contains(@class,'phase-1')]")
#             # FIX 5: original used .get_attribute("class") which is not a Scrapy method;
#             #         correct approach is to grab the class attr via XPath then check text
#             phase1_status = self.checker(
#                 phase1_div.xpath(".//p/text()").get()
#             )
#             phase1_notes = phase1_div.xpath(".//p[2]/text()").get("").strip()

#             # ── Helper: extract one phase block ───────────────────────────────
#             def get_phase(phase_class):
#                 """
#                 Returns (status, ratio, balloting_yn, balloting_ratio) for a phase div.
#                 FIX 6: lambdas were used as values – they were never called, so they would
#                         always be stored as function objects instead of strings.
#                         Replaced with a regular helper function called immediately.
#                 """
#                 div = card.xpath(f".//div[contains(@class,'{phase_class}')]")
#                 if not div:
#                     return "N/A", "N/A", "N/A", "N/A"

#                 status = self.checker(div.xpath(".//p[1]/text()").get())

#                 # Applicants / Vacancies ratio for the phase
#                 applicants = div.xpath(
#                     ".//div[contains(@class,'applicants')]//p[2]/text()"
#                 ).get()
#                 vacancies_in_phase = div.xpath(
#                     ".//div[contains(@class,'vacancies')]//p[2]/text()"
#                 ).get()
#                 # FIX 7: original concatenated directly, crashing on None; use safe_ratio
#                 ratio = self.safe_ratio(applicants, vacancies_in_phase)

#                 # Balloting conducted?
#                 balloting_yn = div.xpath(
#                     ".//div[contains(@class,'balloting')]//i/text()"
#                 ).get("N/A").strip()

#                 # Balloting ratio (only meaningful when balloting == "Yes")
#                 if balloting_yn == "Yes":
#                     b_num = div.xpath(
#                         ".//div[contains(@class,'balloting-ratio')]//p[1]/text()"
#                     ).get()
#                     b_den = div.xpath(
#                         ".//div[contains(@class,'balloting-ratio')]//p[2]/text()"
#                     ).get()
#                     balloting_ratio = self.safe_ratio(b_num, b_den)
#                 else:
#                     balloting_ratio = "N/A"

#                 return status, ratio, balloting_yn, balloting_ratio

#             p2a_status,  p2a_ratio,  p2a_bal,  p2a_bal_ratio  = get_phase("phase-2a")
#             p2b_status,  p2b_ratio,  p2b_bal,  p2b_bal_ratio  = get_phase("phase-2b")
#             p2c_status,  p2c_ratio,  p2c_bal,  p2c_bal_ratio  = get_phase("phase-2c")

#             # ── Phase 2C Supplementary ────────────────────────────────────────
#             p2cs_div = card.xpath(".//div[contains(@class,'phase-2cs')]")
#             p2cs_raw = p2cs_div.xpath(".//p[1]/text()").get()
#             p2cs_status = self.checker(p2cs_raw)

#             if p2cs_status == "No registration was conducted":
#                 p2cs_ratio = "N/A"
#             else:
#                 p2cs_num = p2cs_div.xpath(".//p[4]/text()").get()
#                 p2cs_den = p2cs_div.xpath(".//div[contains(@class,'vacancies')]//p[2]/text()").get()
#                 p2cs_ratio = self.safe_ratio(p2cs_num, p2cs_den)

#             p2cs_bal_yn = p2cs_div.xpath(
#                 ".//div[contains(@class,'balloting')]//i/text()"
#             ).get("N/A").strip()

#             if p2cs_bal_yn == "Yes":
#                 b_num = p2cs_div.xpath(
#                     ".//div[contains(@class,'balloting-ratio')]//p[1]/text()"
#                 ).get()
#                 b_den = p2cs_div.xpath(
#                     ".//div[contains(@class,'balloting-ratio')]//p[2]/text()"
#                 ).get()
#                 p2cs_bal_ratio = self.safe_ratio(b_num, b_den)
#             else:
#                 p2cs_bal_ratio = "N/A"

#             yield SchoolItem(
#                 Name=name,
#                 Vacancies=vacancies,
#                 Phase_1=phase1_status,
#                 Phase_1_notes=phase1_notes,
#                 Phase_2A=p2a_status,
#                 Phase_2A_Ratio=p2a_ratio,
#                 Phase_2A_Balloting=p2a_bal,
#                 Phase_2A_Balloting_ratio=p2a_bal_ratio,
#                 Phase_2B=p2b_status,
#                 Phase_2B_ratio=p2b_ratio,
#                 Phase_2B_Balloting=p2b_bal,
#                 Phase_2B_Balloting_ratio=p2b_bal_ratio,
#                 Phase_2C=p2c_status,
#                 Phase_2C_ratio=p2c_ratio,
#                 Phase_2C_Balloting=p2c_bal,
#                 Phase_2C_Balloting_ratio=p2c_bal_ratio,
#                 Phase_2C_sup=p2cs_status,
#                 Phase_2C_sup_ratio=p2cs_ratio,
#                 Phase_2C_sup_Balloting=p2cs_bal_yn,
#                 Phase_2C_sup_Balloting_ratio=p2cs_bal_ratio,
#             )       

# import scrapy
# from scrapy_playwright.page import PageMethod


# class SchoolItem(scrapy.Item):
#     Name = scrapy.Field()
#     Vacancies = scrapy.Field()
#     Phase_1 = scrapy.Field()
#     Phase_1_notes = scrapy.Field()
#     Phase_2A = scrapy.Field()
#     Phase_2A_Ratio = scrapy.Field()
#     Phase_2A_Balloting = scrapy.Field()
#     Phase_2A_Balloting_ratio = scrapy.Field()
#     Phase_2B = scrapy.Field()
#     Phase_2B_ratio = scrapy.Field()
#     Phase_2B_Balloting = scrapy.Field()
#     Phase_2B_Balloting_ratio = scrapy.Field()
#     Phase_2C = scrapy.Field()
#     Phase_2C_ratio = scrapy.Field()
#     Phase_2C_Balloting = scrapy.Field()
#     Phase_2C_Balloting_ratio = scrapy.Field()
#     Phase_2C_sup = scrapy.Field()
#     Phase_2C_sup_ratio = scrapy.Field()
#     Phase_2C_sup_Balloting = scrapy.Field()
#     Phase_2C_sup_Balloting_ratio = scrapy.Field()


# class ballotSpider(scrapy.Spider):
#     name = "schools"
#     allowed_domains = ["www.moe.gov.sg"]
#     start_urls = ["https://www.moe.gov.sg/primary/p1-registration/past-vacancies-and-balloting-data"]

#     custom_settings = {
#         # ── Playwright middleware ──────────────────────────────────────────────
#         "DOWNLOAD_HANDLERS": {
#             "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#             "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#         },
#         "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
#         "PLAYWRIGHT_BROWSER_TYPE": "chromium",
#         "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},

#         # ── Output ────────────────────────────────────────────────────────────
#         "FEEDS": {
#             "schools.csv": {
#                 "format": "csv",
#                 "item_classes": [SchoolItem],
#                 "overwrite": True,
#                 "fields": [
#                     "Name", "Vacancies",
#                     "Phase_1", "Phase_1_notes",
#                     "Phase_2A", "Phase_2A_Ratio", "Phase_2A_Balloting", "Phase_2A_Balloting_ratio",
#                     "Phase_2B", "Phase_2B_ratio", "Phase_2B_Balloting", "Phase_2B_Balloting_ratio",
#                     "Phase_2C", "Phase_2C_ratio", "Phase_2C_Balloting", "Phase_2C_Balloting_ratio",
#                     "Phase_2C_sup", "Phase_2C_sup_ratio", "Phase_2C_sup_Balloting", "Phase_2C_sup_Balloting_ratio",
#                 ],
#             }
#         },
#         "DOWNLOAD_DELAY": 1.5,
#         "ROBOTSTXT_OBEY": True,
#         "USER_AGENT": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#         ),
#     }

#     def start_requests(self):
#         for url in self.start_urls:
#             yield scrapy.Request(
#                 url,
#                 meta={
#                     "playwright": True,
#                     "playwright_page_methods": [
#                         # Wait until at least one school card is visible in the DOM
#                         PageMethod("wait_for_selector", ".moe-vacancies-ballot-card", timeout=30000),
#                         # Small extra wait for all cards to finish rendering
#                         PageMethod("wait_for_timeout", 2000),
#                     ],
#                 },
#                 callback=self.parse,
#             )

#     # ── Helpers ───────────────────────────────────────────────────────────────

#     def checker(self, text):
#         if text is None:
#             return "N/A"
#         if "All eligible applicants were offered a place" in text:
#             return "All applicants were successful"
#         if "Balloting was not conducted" in text:
#             return "No balloting needed – vacancies not exceeded"
#         if "No registration" in text:
#             return "No registration was conducted"
#         return text.strip()

#     def safe_ratio(self, numerator, denominator):
#         if numerator and denominator:
#             return f"{numerator.strip()}/{denominator.strip()}"
#         return "N/A"

#     # ── Parsing ───────────────────────────────────────────────────────────────

#     def parse(self, response):
#         school_cards = response.css(".moe-vacancies-ballot-card")

#         if not school_cards:
#             self.logger.error(
#                 "Still no school cards after Playwright render. "
#                 "Open the page in a real browser, right-click a school card → "
#                 "Inspect, and find the correct CSS class, then update the selector."
#             )
#             # Dump rendered HTML snippet to help debug selectors
#             self.logger.debug(response.text[:3000])
#             return

#         self.logger.info(f"Found {len(school_cards)} school cards.")

#         for card in school_cards:
#             name      = card.css("h3::text").get("").strip()
#             vacancies = card.css(".total-vacancies p::text").get("").strip()

#             # Phase 1
#             phase1_div    = card.css(".phase-1")
#             phase1_text   = " ".join(phase1_div.css("p::text").getall()).strip()
#             phase1_status = self.checker(phase1_text)
#             phase1_notes  = phase1_div.css("p:nth-child(2)::text").get("").strip()

#             # Generic phase extractor — defined here so it closes over `card`
#             def get_phase(css_class):
#                 div = card.css(f".{css_class}")
#                 if not div:
#                     return "N/A", "N/A", "N/A", "N/A"

#                 status = self.checker(div.css("p:first-child::text").get())

#                 applicants      = div.css(".applicants p:nth-child(2)::text").get()
#                 phase_vacancies = div.css(".vacancies p:nth-child(2)::text").get()
#                 ratio = self.safe_ratio(applicants, phase_vacancies)

#                 balloting_yn = div.css(".balloting i::text").get("N/A").strip()

#                 if balloting_yn == "Yes":
#                     b_num = div.css(".balloting-ratio p:nth-child(1)::text").get()
#                     b_den = div.css(".balloting-ratio p:nth-child(2)::text").get()
#                     balloting_ratio = self.safe_ratio(b_num, b_den)
#                 else:
#                     balloting_ratio = "N/A"

#                 return status, ratio, balloting_yn, balloting_ratio

#             p2a_s, p2a_r, p2a_b, p2a_br = get_phase("phase-2a")
#             p2b_s, p2b_r, p2b_b, p2b_br = get_phase("phase-2b")
#             p2c_s, p2c_r, p2c_b, p2c_br = get_phase("phase-2c")

#             # Phase 2C Supplementary
#             sup        = card.css(".phase-2cs")
#             sup_status = self.checker(sup.css("p:first-child::text").get())

#             if sup_status == "No registration was conducted":
#                 sup_ratio = "N/A"
#             else:
#                 sup_ratio = self.safe_ratio(
#                     sup.css(".applicants p:nth-child(2)::text").get(),
#                     sup.css(".vacancies p:nth-child(2)::text").get(),
#                 )

#             sup_bal_yn = sup.css(".balloting i::text").get("N/A").strip()
#             if sup_bal_yn == "Yes":
#                 sup_bal_ratio = self.safe_ratio(
#                     sup.css(".balloting-ratio p:nth-child(1)::text").get(),
#                     sup.css(".balloting-ratio p:nth-child(2)::text").get(),
#                 )
#             else:
#                 sup_bal_ratio = "N/A"

#             yield SchoolItem(
#                 Name=name,
#                 Vacancies=vacancies,
#                 Phase_1=phase1_status,
#                 Phase_1_notes=phase1_notes,
#                 Phase_2A=p2a_s,
#                 Phase_2A_Ratio=p2a_r,
#                 Phase_2A_Balloting=p2a_b,
#                 Phase_2A_Balloting_ratio=p2a_br,
#                 Phase_2B=p2b_s,
#                 Phase_2B_ratio=p2b_r,
#                 Phase_2B_Balloting=p2b_b,
#                 Phase_2B_Balloting_ratio=p2b_br,
#                 Phase_2C=p2c_s,
#                 Phase_2C_ratio=p2c_r,
#                 Phase_2C_Balloting=p2c_b,
#                 Phase_2C_Balloting_ratio=p2c_br,
#                 Phase_2C_sup=sup_status,
#                 Phase_2C_sup_ratio=sup_ratio,
#                 Phase_2C_sup_Balloting=sup_bal_yn,
#                 Phase_2C_sup_Balloting_ratio=sup_bal_ratio,
#             )
# """


# """
# MOE P1 Balloting Spider – with Playwright + Pagination
# =======================================================

# SETUP (run once in your terminal before crawling):
#     pip install scrapy-playwright
#     playwright install chromium

# RUN:
#     python -m scrapy crawl schools
# """

# import scrapy
# import scrapy_playwright
# from scrapy_playwright.page import PageMethod


# class SchoolItem(scrapy.Item):
#     Name = scrapy.Field()
#     Vacancies = scrapy.Field()
#     Phase_1 = scrapy.Field()
#     Phase_1_notes = scrapy.Field()
#     Phase_2A = scrapy.Field()
#     Phase_2A_Ratio = scrapy.Field()
#     Phase_2A_Balloting = scrapy.Field()
#     Phase_2A_Balloting_ratio = scrapy.Field()
#     Phase_2B = scrapy.Field()
#     Phase_2B_ratio = scrapy.Field()
#     Phase_2B_Balloting = scrapy.Field()
#     Phase_2B_Balloting_ratio = scrapy.Field()
#     Phase_2C = scrapy.Field()
#     Phase_2C_ratio = scrapy.Field()
#     Phase_2C_Balloting = scrapy.Field()
#     Phase_2C_Balloting_ratio = scrapy.Field()
#     Phase_2C_sup = scrapy.Field()
#     Phase_2C_sup_ratio = scrapy.Field()
#     Phase_2C_sup_Balloting = scrapy.Field()
#     Phase_2C_sup_Balloting_ratio = scrapy.Field()


# class ballotSpider(scrapy.Spider):
#     name = "schools"
#     allowed_domains = ["www.moe.gov.sg"]
#     start_urls = ["https://www.moe.gov.sg/primary/p1-registration/past-vacancies-and-balloting-data"]

#     custom_settings = {
#         "DOWNLOAD_HANDLERS": {
#             "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#             "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#         },
#         "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
#         "PLAYWRIGHT_BROWSER_TYPE": "chromium",
#         "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
#         "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
#         "FEEDS": {
#             "schools.csv": {
#                 "format": "csv",
#                 "item_classes": [SchoolItem],
#                 "overwrite": True,
#                 "fields": [
#                     "Name", "Vacancies",
#                     "Phase_1", "Phase_1_notes",
#                     "Phase_2A", "Phase_2A_Ratio", "Phase_2A_Balloting", "Phase_2A_Balloting_ratio",
#                     "Phase_2B", "Phase_2B_ratio", "Phase_2B_Balloting", "Phase_2B_Balloting_ratio",
#                     "Phase_2C", "Phase_2C_ratio", "Phase_2C_Balloting", "Phase_2C_Balloting_ratio",
#                     "Phase_2C_sup", "Phase_2C_sup_ratio", "Phase_2C_sup_Balloting", "Phase_2C_sup_Balloting_ratio",
#                 ],
#             }
#         },
#         "ROBOTSTXT_OBEY": True,
#         "DOWNLOAD_DELAY": 1.0,
#         "USER_AGENT": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#         ),
#     }

#     # ── Entry point ───────────────────────────────────────────────────────────

#     def start_requests(self):
#         yield scrapy.Request(
#             self.start_urls[0],
#             meta={
#                 "playwright": True,
#                 "playwright_include_page": True,
#                 "playwright_page_methods": [
#                     PageMethod("wait_for_selector", ".moe-vacancies-ballot-card", timeout=30000),
#                     PageMethod("wait_for_timeout", 1500),
#                 ],
#             },
#             callback=self.parse_page,
#             errback=self.handle_error,
#         )

#     # ── Page parser ───────────────────────────────────────────────────────────

#     async def parse_page(self, response):
#         page = response.meta["playwright_page"]
#         results = []

#         pag_text = response.css("p.pag-text::text").get("")
#         self.logger.info(f"Scraping page: {pag_text or '(no pagination text found)'}")

#         for card in response.css(".moe-vacancies-ballot-card"):
#             results.extend(self._parse_card(card))

#         next_btn = await page.query_selector("button.btn-pag-next")

#         if next_btn is None:
#             self.logger.info("No Next button found – done.")
#             await page.close()
#             return results

#         is_disabled   = await next_btn.get_attribute("disabled")
#         aria_disabled = await next_btn.get_attribute("aria-disabled")

#         if is_disabled is not None or aria_disabled == "true":
#             self.logger.info("Next button disabled – reached last page.")
#             await page.close()
#             return results

#         await next_btn.click()
#         await page.wait_for_selector(".moe-vacancies-ballot-card", timeout=30000)
#         await page.wait_for_timeout(1200)

#         new_html = await page.content()
#         new_response = scrapy.http.HtmlResponse(
#             url=page.url,
#             body=new_html,
#             encoding="utf-8",
#             request=scrapy.http.Request(
#                 page.url,
#                 meta={"playwright_page": page},
#             ),
#         )
#         new_response.meta["playwright_page"] = page

#         next_results = await self.parse_page(new_response)
#         results.extend(next_results)
#         return results

#     # ── Error handler ─────────────────────────────────────────────────────────

#     async def handle_error(self, failure):
#         page = failure.request.meta.get("playwright_page")
#         if page:
#             await page.close()
#         self.logger.error(f"Request failed: {failure.value}")

#     # ── Helpers ───────────────────────────────────────────────────────────────

#     def get_info_data(self, div, label):
#         """
#         The page uses a label/value pattern:
#             <span class="info-title">Vacancies</span>
#             <span class="info-data">30</span>

#         This finds the .info-title whose text matches `label`, then returns
#         the text of the immediately following .info-data sibling.

#         Using XPath `following-sibling` is the most robust way to link a
#         label to its value without relying on brittle nth-child positions.
#         """
#         return div.xpath(
#             f".//*[contains(@class,'info-title') and "
#             f"normalize-space(.)='{label}']"
#             f"/following-sibling::*[contains(@class,'info-data')][1]"
#             f"//text()"
#             ).get("").strip()

#     def get_phase(self, card, css_class):
#         """
#         All phases share the class `moe-vacancies-ballot-card__phase`.
#         Returns a list of (status, ratio, bal_yn, bal_ratio) tuples, one per
#         phase div, so callers can access by index:
#             [0] = Phase 1
#             [1] = Phase 2A
#             [2] = Phase 2B
#             [3] = Phase 2C
#             [4] = Phase 2C Supplementary

#         Padded to length 5 with ("N/A","N/A","N/A","N/A") so index access
#         never raises an IndexError.
#         """
#         phase_divs = card.css(f".{css_class}")
#         results = []

#         for div in phase_divs:
#             status = self.checker(div.css("p:first-child::text").get())

#             applicants = self.get_info_data(div, "Applicants")
#             vacancies  = self.get_info_data(div, "Vacancies")
#             ratio = self.safe_ratio(applicants, vacancies)

#             bal_yn = div.css(".moe-vacancies-ballot-card__balloting i::text").get("N/A").strip()

#             if bal_yn == "Yes":
#                 bal_div    = div.css(".balloting-ratio")
#                 successful = self.get_info_data(bal_div, "Successful Applicants")
#                 total_bal  = self.get_info_data(bal_div, "Total Applicants in Ballot")
#                 bal_ratio  = self.safe_ratio(successful, total_bal)
#             else:
#                 bal_ratio = "N/A"

#             results.append((status, ratio, bal_yn, bal_ratio))

#         # Pad so [0]–[4] are always safe to access
#         while len(results) < 5:
#             results.append(("N/A", "N/A", "N/A", "N/A"))

#         return results

#     def checker(self, text):
#         if not text:
#             return "N/A"
#         text = text.strip()
#         if "All eligible applicants were offered a place" in text:
#             return "All applicants were successful"
#         if "Balloting was not conducted" in text:
#             return "No balloting needed – vacancies not exceeded"
#         if "No registration" in text:
#             return "No registration was conducted"
#         return text

#     def safe_ratio(self, numerator, denominator):
#         if numerator and denominator:
#             return f"{numerator.strip()}/{denominator.strip()}"
#         return "N/A"

#     # ── Card parser ───────────────────────────────────────────────────────────

#     def _parse_card(self, card):
#         name      = card.css("h3::text").get("").strip()
#         vacancies = card.css(".moe-vacancies-ballot-card__total-vacancies p::text").get("").strip()

#         # Phase 1 is the first phase div; it only has a status and optional notes
#         # .eq() does not exist on SelectorList — use [0] then wrap in a list
#         phase1_divs   = card.css(".moe-vacancies-ballot-card__phase")
#         phase1_div    = phase1_divs[0] if phase1_divs else None
#         phase1_status = self.checker(" ".join(phase1_div.css("p::text").getall())) if phase1_div else "N/A"
#         phase1_notes  = phase1_div.css("p:nth-child(2)::text").get("").strip() if phase1_div else ""

#         # Call once and access by index — avoids traversing the DOM 4 times
#         phases = self.get_phase(card, "moe-vacancies-ballot-card__phase")
#         p2a_s, p2a_r, p2a_b, p2a_br = phases[1]
#         p2b_s, p2b_r, p2b_b, p2b_br = phases[2]
#         p2c_s, p2c_r, p2c_b, p2c_br = phases[3]

#         # Phase 2C Supplementary
#         sup_s, sup_r, sup_b, sup_br = phases[4]
#         if sup_s == "No registration was conducted":
#             sup_r = "N/A"

#         return [SchoolItem(
#             Name=name,
#             Vacancies=vacancies,
#             Phase_1=phase1_status,
#             Phase_1_notes=phase1_notes,
#             Phase_2A=p2a_s,
#             Phase_2A_Ratio=p2a_r,
#             Phase_2A_Balloting=p2a_b,
#             Phase_2A_Balloting_ratio=p2a_br,
#             Phase_2B=p2b_s,
#             Phase_2B_ratio=p2b_r,
#             Phase_2B_Balloting=p2b_b,
#             Phase_2B_Balloting_ratio=p2b_br,
#             Phase_2C=p2c_s,
#             Phase_2C_ratio=p2c_r,
#             Phase_2C_Balloting=p2c_b,
#             Phase_2C_Balloting_ratio=p2c_br,
#             Phase_2C_sup=sup_s,
#             Phase_2C_sup_ratio=sup_r,
#             Phase_2C_sup_Balloting=sup_b,
#             Phase_2C_sup_Balloting_ratio=sup_br,
#         )]













"""
MOE P1 Balloting Spider – with Playwright + Pagination
=======================================================

SETUP (run once in your terminal before crawling):
    pip install scrapy-playwright
    playwright install chromium

RUN:
    python -m scrapy crawl schools
"""

import scrapy
import scrapy_playwright
from scrapy_playwright.page import PageMethod


class SchoolItem(scrapy.Item):
    Name = scrapy.Field()
    Vacancies = scrapy.Field()
    Phase_1 = scrapy.Field()
    Phase_1_notes = scrapy.Field()
    Phase_2A = scrapy.Field()
    Phase_2A_Ratio = scrapy.Field()
    Phase_2A_Balloting = scrapy.Field()
    Phase_2A_Balloting_ratio = scrapy.Field()
    Phase_2B = scrapy.Field()
    Phase_2B_ratio = scrapy.Field()
    Phase_2B_Balloting = scrapy.Field()
    Phase_2B_Balloting_ratio = scrapy.Field()
    Phase_2C = scrapy.Field()
    Phase_2C_ratio = scrapy.Field()
    Phase_2C_Balloting = scrapy.Field()
    Phase_2C_Balloting_ratio = scrapy.Field()
    Phase_2C_sup = scrapy.Field()
    Phase_2C_sup_ratio = scrapy.Field()
    Phase_2C_sup_Balloting = scrapy.Field()
    Phase_2C_sup_Balloting_ratio = scrapy.Field()


class ballotSpider(scrapy.Spider):
    name = "schools"
    allowed_domains = ["www.moe.gov.sg"]
    start_urls = ["https://www.moe.gov.sg/primary/p1-registration/past-vacancies-and-balloting-data"]

    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        "FEEDS": {
            "schools.csv": {
                "format": "csv",
                "item_classes": [SchoolItem],
                "overwrite": True,
                "fields": [
                    "Name", "Vacancies",
                    "Phase_1", "Phase_1_notes",
                    "Phase_2A", "Phase_2A_Ratio", "Phase_2A_Balloting", "Phase_2A_Balloting_ratio",
                    "Phase_2B", "Phase_2B_ratio", "Phase_2B_Balloting", "Phase_2B_Balloting_ratio",
                    "Phase_2C", "Phase_2C_ratio", "Phase_2C_Balloting", "Phase_2C_Balloting_ratio",
                    "Phase_2C_sup", "Phase_2C_sup_ratio", "Phase_2C_sup_Balloting", "Phase_2C_sup_Balloting_ratio",
                ],
            }
        },
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # ── Entry point ───────────────────────────────────────────────────────────

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls[0],
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", ".moe-vacancies-ballot-card", timeout=30000),
                    PageMethod("wait_for_timeout", 1500),
                ],
            },
            callback=self.parse_page,
            errback=self.handle_error,
        )

    # ── Page parser ───────────────────────────────────────────────────────────

    async def parse_page(self, response):
        page = response.meta["playwright_page"]
        results = []

        pag_text = response.css("p.pag-text::text").get("")
        self.logger.info(f"Scraping page: {pag_text or '(no pagination text found)'}")

        for card in response.css(".moe-vacancies-ballot-card"):
            results.extend(self._parse_card(card))

        next_btn = await page.query_selector("button.btn-pag-next")

        if next_btn is None:
            self.logger.info("No Next button found – done.")
            await page.close()
            return results

        is_disabled   = await next_btn.get_attribute("disabled")
        aria_disabled = await next_btn.get_attribute("aria-disabled")

        if is_disabled is not None or aria_disabled == "true":
            self.logger.info("Next button disabled – reached last page.")
            await page.close()
            return results

        await next_btn.click()
        await page.wait_for_selector(".moe-vacancies-ballot-card", timeout=30000)
        await page.wait_for_timeout(1200)

        new_html = await page.content()
        new_response = scrapy.http.HtmlResponse(
            url=page.url,
            body=new_html,
            encoding="utf-8",
            request=scrapy.http.Request(
                page.url,
                meta={"playwright_page": page},
            ),
        )
        new_response.meta["playwright_page"] = page

        next_results = await self.parse_page(new_response)
        results.extend(next_results)
        return results

    # ── Error handler ─────────────────────────────────────────────────────────

    async def handle_error(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        self.logger.error(f"Request failed: {failure.value}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_info_data(self, div, label):
        """
        The page uses a label/value pattern:
            <span class="info-title">Vacancies</span>
            <span class="info-data">30</span>

        This finds the .info-title whose text matches `label`, then returns
        the text of the immediately following .info-data sibling.

        Using XPath `following-sibling` is the most robust way to link a
        label to its value without relying on brittle nth-child positions.
        """
        return div.xpath(
            f".//*[contains(@class,'info-title') and "
            f"normalize-space(.)='{label}']"
            f"/following-sibling::*[contains(@class,'info-data')][1]"
            f"//text()"
            ).get("").strip()

    def get_phase(self, card, css_class):
        """
        All phases share the class `moe-vacancies-ballot-card__phase`.
        Returns a list of (status, ratio, bal_yn, bal_ratio) tuples, one per
        phase div, so callers can access by index:
            [0] = Phase 1
            [1] = Phase 2A
            [2] = Phase 2B
            [3] = Phase 2C
            [4] = Phase 2C Supplementary

        Padded to length 5 with ("N/A","N/A","N/A","N/A") so index access
        never raises an IndexError.
        """
        phase_divs = card.css(f".{css_class}")
        results = []

        for div in phase_divs:
            status = self.checker(div.css("h4::attr(class)").get(default="N/A").strip())#.getall())
            applicants = self.get_info_data(div, "Applicants")
            vacancies  = self.get_info_data(div, "Vacancies")
            ratio = self.safe_ratio(applicants, vacancies)

            bal_yn = div.css(".moe-vacancies-ballot-card__balloting span::text").get("N/A").strip()

            if bal_yn == "Yes":
                bal_div = div.xpath(".//*[contains(@class,'info-block-balloted')]")
                successful = self.get_info_data(bal_div, "Balloting applicants")
                total_bal  = self.get_info_data(bal_div, "Vacancies for ballot")
                bal_ratio  = self.safe_ratio(successful, total_bal)
            else:
                bal_ratio = "N/A"

            results.append((status, ratio, bal_yn, bal_ratio))

        # Pad so [0]–[4] are always safe to access
        while len(results) < 5:
            results.append(("N/A", "N/A", "N/A", "N/A"))

        return results

    def checker(self, text):
        if not text:
            return "N/A"
        text = text.strip()
        if "moe-vacancies-ballot-card--dot-active-in-phase-green" in text:
            return "All applicants were successful"
        if "moe-vacancies-ballot-card--dot-active-in-phase-red" in text:
            return "There were more applicants than vacancies"
        if "VacanciesBallot_triangle__3pm5V" in text:
            return "No registration was conducted"
        return text

    def safe_ratio(self, numerator, denominator):
        if numerator and denominator:
            return f"{numerator.strip()}/{denominator.strip()}"
        return "N/A"

    # ── Card parser ───────────────────────────────────────────────────────────

    def _parse_card(self, card):
        name      = card.css("h3::text").get("").strip()
        vacancies = card.css(".moe-vacancies-ballot-card__total-vacancies p::text").get("").strip()

        # ── DEBUG: runs once on the first card to reveal real DOM structure ──
        # Remove this block once selectors are confirmed correct.
        if not hasattr(self, '_debug_logged'):
            self._debug_logged = True
            phase_divs = card.css(".moe-vacancies-ballot-card__phase")
            self.logger.warning("=== DEBUG: %d phase divs found ===", len(phase_divs))
            for i, div in enumerate(phase_divs):
                self.logger.warning("--- Phase div [%d] HTML ---\n%s", i, div.get())
        # ── END DEBUG ────────────────────────────────────────────────────────

        # Phase 1 is the first phase div; it only has a status and optional notes
        # .eq() does not exist on SelectorList — use [0] then wrap in a list
        phase1_divs   = card.css(".moe-vacancies-ballot-card__phase")
        phase1_div    = phase1_divs[0] if phase1_divs else None
        phase1_status = self.checker(" ".join(phase1_div.css("p::text").getall())) if phase1_div else "N/A"
        phase1_notes  = phase1_div.css("p:nth-child(2)::text").get("").strip() if phase1_div else ""

        # Call once and access by index — avoids traversing the DOM 4 times
        phases = self.get_phase(card, "moe-vacancies-ballot-card__phase")
        p2a_s, p2a_r, p2a_b, p2a_br = phases[1]
        p2b_s, p2b_r, p2b_b, p2b_br = phases[2]
        p2c_s, p2c_r, p2c_b, p2c_br = phases[3]

        # Phase 2C Supplementary
        sup_s, sup_r, sup_b, sup_br = phases[4]
        if sup_s == "No registration was conducted":
            sup_r = "N/A"

        return [SchoolItem(
            Name=name,
            Vacancies=vacancies,
            Phase_1=phase1_status,
            Phase_1_notes=phase1_notes,
            Phase_2A=p2a_s,
            Phase_2A_Ratio=p2a_r,
            Phase_2A_Balloting=p2a_b,
            Phase_2A_Balloting_ratio=p2a_br,
            Phase_2B=p2b_s,
            Phase_2B_ratio=p2b_r,
            Phase_2B_Balloting=p2b_b,
            Phase_2B_Balloting_ratio=p2b_br,
            Phase_2C=p2c_s,
            Phase_2C_ratio=p2c_r,
            Phase_2C_Balloting=p2c_b,
            Phase_2C_Balloting_ratio=p2c_br,
            Phase_2C_sup=sup_s,
            Phase_2C_sup_ratio=sup_r,
            Phase_2C_sup_Balloting=sup_b,
            Phase_2C_sup_Balloting_ratio=sup_br,
        )]






























# MOE P1 Balloting Spider – with Playwright + Pagination
# =======================================================

# SETUP (run once in your terminal before crawling):
#     pip install scrapy-playwright
#     playwright install chromium

# RUN:
#     python -m scrapy crawl schools
# """

# import scrapy
# import scrapy_playwright
# from scrapy_playwright.page import PageMethod


# class SchoolItem(scrapy.Item):
#     Name = scrapy.Field()
#     Vacancies = scrapy.Field()
#     Phase_1 = scrapy.Field()
#     Phase_1_notes = scrapy.Field()
#     Phase_2A = scrapy.Field()
#     Phase_2A_Ratio = scrapy.Field()
#     Phase_2A_Balloting = scrapy.Field()
#     Phase_2A_Balloting_ratio = scrapy.Field()
#     Phase_2B = scrapy.Field()
#     Phase_2B_ratio = scrapy.Field()
#     Phase_2B_Balloting = scrapy.Field()
#     Phase_2B_Balloting_ratio = scrapy.Field()
#     Phase_2C = scrapy.Field()
#     Phase_2C_ratio = scrapy.Field()
#     Phase_2C_Balloting = scrapy.Field()
#     Phase_2C_Balloting_ratio = scrapy.Field()
#     Phase_2C_sup = scrapy.Field()
#     Phase_2C_sup_ratio = scrapy.Field()
#     Phase_2C_sup_Balloting = scrapy.Field()
#     Phase_2C_sup_Balloting_ratio = scrapy.Field()


# class ballotSpider(scrapy.Spider):
#     name = "schools"
#     allowed_domains = ["www.moe.gov.sg"]
#     start_urls = ["https://www.moe.gov.sg/primary/p1-registration/past-vacancies-and-balloting-data"]

#     custom_settings = {
#         "DOWNLOAD_HANDLERS": {
#             "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#             "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#         },
#         "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
#         "PLAYWRIGHT_BROWSER_TYPE": "chromium",
#         "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
#         "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
#         "FEEDS": {
#             "schools.csv": {
#                 "format": "csv",
#                 "item_classes": [SchoolItem],
#                 "overwrite": True,
#                 "fields": [
#                     "Name", "Vacancies",
#                     "Phase_1", "Phase_1_notes",
#                     "Phase_2A", "Phase_2A_Ratio", "Phase_2A_Balloting", "Phase_2A_Balloting_ratio",
#                     "Phase_2B", "Phase_2B_ratio", "Phase_2B_Balloting", "Phase_2B_Balloting_ratio",
#                     "Phase_2C", "Phase_2C_ratio", "Phase_2C_Balloting", "Phase_2C_Balloting_ratio",
#                     "Phase_2C_sup", "Phase_2C_sup_ratio", "Phase_2C_sup_Balloting", "Phase_2C_sup_Balloting_ratio",
#                 ],
#             }
#         },
#         "ROBOTSTXT_OBEY": True,
#         "DOWNLOAD_DELAY": 1.0,
#         "USER_AGENT": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#         ),
#     }

#     # ── Entry point ───────────────────────────────────────────────────────────

#     def start_requests(self):
#         yield scrapy.Request(
#             self.start_urls[0],
#             meta={
#                 "playwright": True,
#                 "playwright_include_page": True,
#                 "playwright_page_methods": [
#                     PageMethod("wait_for_selector", ".moe-vacancies-ballot-card", timeout=30000),
#                     PageMethod("wait_for_timeout", 1500),
#                 ],
#             },
#             callback=self.parse_page,
#             errback=self.handle_error,
#         )

#     # ── Page parser ───────────────────────────────────────────────────────────

#     async def parse_page(self, response):
#         page = response.meta["playwright_page"]
#         results = []

#         pag_text = response.css("p.pag-text::text").get("")
#         self.logger.info(f"Scraping page: {pag_text or '(no pagination text found)'}")

#         for card in response.css(".moe-vacancies-ballot-card"):
#             results.extend(self._parse_card(card))

#         next_btn = await page.query_selector("button.btn-pag-next")

#         if next_btn is None:
#             self.logger.info("No Next button found – done.")
#             await page.close()
#             return results

#         is_disabled   = await next_btn.get_attribute("disabled")
#         aria_disabled = await next_btn.get_attribute("aria-disabled")

#         if is_disabled is not None or aria_disabled == "true":
#             self.logger.info("Next button disabled – reached last page.")
#             await page.close()
#             return results

#         await next_btn.click()
#         await page.wait_for_selector(".moe-vacancies-ballot-card", timeout=30000)
#         await page.wait_for_timeout(1200)

#         new_html = await page.content()
#         new_response = scrapy.http.HtmlResponse(
#             url=page.url,
#             body=new_html,
#             encoding="utf-8",
#             request=scrapy.http.Request(
#                 page.url,
#                 meta={"playwright_page": page},
#             ),
#         )
#         new_response.meta["playwright_page"] = page

#         next_results = await self.parse_page(new_response)
#         results.extend(next_results)
#         return results

#     # ── Error handler ─────────────────────────────────────────────────────────

#     async def handle_error(self, failure):
#         page = failure.request.meta.get("playwright_page")
#         if page:
#             await page.close()
#         self.logger.error(f"Request failed: {failure.value}")

#     # ── Helpers ───────────────────────────────────────────────────────────────

#     def get_info_data(self, div, label):
#         """
#         The page uses a label/value pattern:
#             <span class="info-title">Vacancies</span>
#             <span class="info-data">30</span>

#         This finds the .info-title whose text matches `label`, then returns
#         the text of the immediately following .info-data sibling.

#         Using XPath `following-sibling` is the most robust way to link a
#         label to its value without relying on brittle nth-child positions.
#         """
#         return div.xpath(
#              f".//*[contains(@class,'info-title') and "
#              f"normalize-space(.)='{label}']"
#              f"/following-sibling::*[contains(@class,'info-data')][1]"
#              f"//text()"
#              ).get("").strip()

#     def get_phase(self, card, css_class):
#         """
#         Extracts all data for a single registration phase block.

#         DOM structure expected:
#             <div class="... {css_class} ...">
#                 <p>Phase status text</p>

#                 <!-- Applicants / Vacancies info-pair -->
#                 <div class="info-pair">
#                     <span class="info-title">Applicants</span>
#                     <span class="info-data">45</span>
#                 </div>
#                 <div class="info-pair">
#                     <span class="info-title">Vacancies</span>
#                     <span class="info-data">40</span>
#                 </div>

#                 <!-- Balloting section (only present when balloting occurred) -->
#                 <div class="moe-vacancies-ballot-card__balloting">
#                     <i>Yes</i>   ← or "No"
#                 </div>

#                 <!-- Balloting ratio (only present when balloting == Yes) -->
#                 <div class="balloting-ratio">
#                     <div class="info-pair">
#                         <span class="info-title">Successful Applicants</span>
#                         <span class="info-data">30</span>
#                     </div>
#                     <div class="info-pair">
#                         <span class="info-title">Total Applicants in Ballot</span>
#                         <span class="info-data">45</span>
#                     </div>
#                 </div>
#             </div>
#         """
#         div = card.css(f".{css_class}")
#         if not div:
#             return "N/A", "N/A", "N/A", "N/A"

#         # Phase status (e.g. "All eligible applicants were offered a place.")
#         status = self.checker(div.css("p:first-child::text").get())

#         # Applicants and Vacancies — look up by their info-title label text
#         applicants = self.get_info_data(div, "Applicants")
#         vacancies  = self.get_info_data(div, "Vacancies")
#         ratio = self.safe_ratio(applicants, vacancies)

#         # Balloting yes/no — stored as text inside an <i> tag
#         bal_yn = div.css(".moe-vacancies-ballot-card__balloting i::text").get("N/A").strip()

#         # Balloting ratio — only present when balloting was conducted
#         if bal_yn == "Yes":
#             bal_div = div.css(".balloting-ratio")
#             successful = self.get_info_data(bal_div, "Successful Applicants")
#             total_bal  = self.get_info_data(bal_div, "Total Applicants in Ballot")
#             bal_ratio  = self.safe_ratio(successful, total_bal)
#         else:
#             bal_ratio = "N/A"

#         return status, ratio, bal_yn, bal_ratio

#     def checker(self, text):
#         if not text:
#             return "N/A"
#         text = text.strip()
#         if "All eligible applicants were offered a place" in text:
#             return "All applicants were successful"
#         if "Balloting was not conducted" in text:
#             return "No balloting needed – vacancies not exceeded"
#         if "No registration" in text:
#             return "No registration was conducted"
#         return text

#     def safe_ratio(self, numerator, denominator):
#         if numerator and denominator:
#             return f"{numerator.strip()}/{denominator.strip()}"
#         return "N/A"

#     # ── Card parser ───────────────────────────────────────────────────────────

#     def _parse_card(self, card):
#         name      = card.css("h3::text").get("").strip()
#         vacancies = card.css(".moe-vacancies-ballot-card__total-vacancies p::text").get("").strip()

#         # Phase 1 is the first phase div; it only has a status and optional notes
#         # .eq() does not exist on SelectorList — use [0] then wrap in a list
#         phase1_divs   = card.css(".moe-vacancies-ballot-card__phase")
#         phase1_div    = phase1_divs[0] if phase1_divs else None
#         phase1_status = self.checker(" ".join(phase1_div.css("p::text").getall())) if phase1_div else "N/A"
#         phase1_notes  = phase1_div.css("p:nth-child(2)::text").get("").strip() if phase1_div else ""

#         p2a_s, p2a_r, p2a_b, p2a_br = self.get_phase(card, "phase-2a")
#         p2b_s, p2b_r, p2b_b, p2b_br = self.get_phase(card, "phase-2b")
#         p2c_s, p2c_r, p2c_b, p2c_br = self.get_phase(card, "phase-2c")

#         # Phase 2C Supplementary — same structure, separate class
#         sup_s, sup_r, sup_b, sup_br = self.get_phase(card, "phase-2cs")
#         # Override ratio to N/A when no registration was conducted
#         if sup_s == "No registration was conducted":
#             sup_r = "N/A"

#         return [SchoolItem(
#             Name=name,
#             Vacancies=vacancies,
#             Phase_1=phase1_status,
#             Phase_1_notes=phase1_notes,
#             Phase_2A=p2a_s,
#             Phase_2A_Ratio=p2a_r,
#             Phase_2A_Balloting=p2a_b,
#             Phase_2A_Balloting_ratio=p2a_br,
#             Phase_2B=p2b_s,
#             Phase_2B_ratio=p2b_r,
#             Phase_2B_Balloting=p2b_b,
#             Phase_2B_Balloting_ratio=p2b_br,
#             Phase_2C=p2c_s,
#             Phase_2C_ratio=p2c_r,
#             Phase_2C_Balloting=p2c_b,
#             Phase_2C_Balloting_ratio=p2c_br,
#             Phase_2C_sup=sup_s,
#             Phase_2C_sup_ratio=sup_r,
#             Phase_2C_sup_Balloting=sup_b,
#             Phase_2C_sup_Balloting_ratio=sup_br,
#         )]
