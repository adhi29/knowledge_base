"""
Stub connectors for enterprise sources (SharePoint, Confluence, Jira, Outlook).
These are placeholders that log what they would do — to be implemented with
real API credentials in production.
"""
from src.ingestion.connectors.base import BaseConnector, RawDocument


class SharePointConnector(BaseConnector):
    """
    Connects to SharePoint via Microsoft Graph API (delta query for incremental sync).
    Requires: SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET,
              SHAREPOINT_SITE_ID in .env
    """
    def __init__(self, site_id: str, drive_id: str, **kwargs):
        self.site_id = site_id
        self.drive_id = drive_id

    def fetch(self) -> list[RawDocument]:
        print("[SharePointConnector] STUB — Requires Microsoft Graph API credentials.")
        print(f"  Would sync site_id={self.site_id}, drive_id={self.drive_id}")
        return []


class ConfluenceConnector(BaseConnector):
    """
    Connects to Confluence Cloud/Server REST API with page versioning support.
    Requires: CONFLUENCE_URL, CONFLUENCE_USER, CONFLUENCE_API_TOKEN in .env
    """
    def __init__(self, space_key: str, **kwargs):
        self.space_key = space_key

    def fetch(self) -> list[RawDocument]:
        print("[ConfluenceConnector] STUB — Requires Confluence API credentials.")
        print(f"  Would sync space_key={self.space_key}")
        return []


class JiraConnector(BaseConnector):
    """
    Connects to Jira/ServiceNow for ticket and KB article ingestion.
    Requires: JIRA_URL, JIRA_USER, JIRA_API_TOKEN in .env
    """
    def __init__(self, project_key: str, **kwargs):
        self.project_key = project_key

    def fetch(self) -> list[RawDocument]:
        print("[JiraConnector] STUB — Requires Jira API credentials.")
        print(f"  Would sync project_key={self.project_key}")
        return []


class OutlookConnector(BaseConnector):
    """
    Connects to Outlook/Exchange via Microsoft Graph API.
    Requires: OUTLOOK_TENANT_ID, OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET in .env
    """
    def __init__(self, mailbox: str, folder: str = "Inbox", **kwargs):
        self.mailbox = mailbox
        self.folder = folder

    def fetch(self) -> list[RawDocument]:
        print("[OutlookConnector] STUB — Requires Microsoft Graph API credentials.")
        print(f"  Would sync mailbox={self.mailbox}, folder={self.folder}")
        return []
