"""Closed positions from READ-T36 R2/R3; later-page behaviour is unobserved."""

URL = "https://eservices.qfc.qa/qfcpublicregister/publicregister.aspx"
PROJECTION = "fc_company_pane@v1"
PRODUCER = "fc_register_paged_capture@v1"
COLUMNS = (
    ("qfc_number", "string"),
    ("company_name", "string"),
    ("company_name_ar", "string"),
    ("metadata", "string"),
    ("licence_status", "string"),
)
PAGERS = ("PrCompanyPager1", "PrCompanyPager")
TARGETS = tuple(p + "$ctl02$ctl00" for p in PAGERS)
# Hidden-state names await activation review: the saved reading omitted them.
STATE_FIELDS = ("__VIEWSTATE", "__EVENTVALIDATION", "__EVENTTARGET", "__EVENTARGUMENT")
SHAPE = {
    "pane": "div.pr-results-list",
    "card": "div.pr-result-card",
    "fields": {
        "qfc_number": "div.pr-result-number > a.pr-num-value",
        "company_name": "div.pr-company-name > a",
        "company_name_ar": "span.pr-company-name-ar > a",
        "metadata": "div.pr-result-meta",
        "licence_status": "div.pr-result-status > span.licence-text",
    },
    "pager_targets": list(TARGETS),
    "form_fields": list(STATE_FIELDS),
    "progress_fields": ["shown_page", "continuation"],
    "projection": PROJECTION,
    "producer": PRODUCER,
}
