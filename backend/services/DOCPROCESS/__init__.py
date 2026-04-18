from .ADEClient import get_ade_client
from .docling_client import get_docling_client

def process_with_ade(file_path):
    return get_ade_client().process_document(file_path)

def process_with_docling(file_path, report_type="lab_report"):
    return get_docling_client().process_document(file_path, report_type)
