import json
from dataclasses import dataclass, field
from typing import List, Optional # Changed from list[Lead] to List[Lead] for older Python compatibility if needed
import logging

logger = logging.getLogger(__name__)

@dataclass
class Lead:
    """
    Represents a sales lead with contact and professional information.
    """
    id: str
    name: str
    phone_number: str
    company_name: str
    role: str
    linkedin_url: str
    custom_notes: str = field(default="") # Allow custom_notes to be optional

def load_leads(filepath: str = "data/leads.json") -> List[Lead]:
    """
    Loads leads from a JSON file.

    Args:
        filepath: The path to the JSON file containing lead data.

    Returns:
        A list of Lead objects.

    Raises:
        FileNotFoundError: If the specified filepath does not exist.
        ValueError: If the JSON data is malformed or missing required fields.
    """
    leads: List[Lead] = []
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.error(f"Invalid JSON format in {filepath}: Expected a list of leads.")
            raise ValueError(f"Invalid JSON format in {filepath}: Expected a list of leads.")

        for lead_data in data:
            if not isinstance(lead_data, dict):
                logger.warning(f"Skipping invalid lead entry (not a dict) in {filepath}: {lead_data}")
                continue
            try:
                # Ensure all required fields are present before creating Lead instance
                required_fields = ['id', 'name', 'phone_number', 'company_name', 'role', 'linkedin_url']
                missing_fields = [rf for rf in required_fields if rf not in lead_data]
                if missing_fields:
                    logger.warning(f"Skipping lead due to missing fields {missing_fields} in {filepath}: {lead_data.get('id', 'N/A')}")
                    continue

                lead = Lead(
                    id=lead_data['id'],
                    name=lead_data['name'],
                    phone_number=lead_data['phone_number'],
                    company_name=lead_data['company_name'],
                    role=lead_data['role'],
                    linkedin_url=lead_data['linkedin_url'],
                    custom_notes=lead_data.get('custom_notes', "") # Use .get for optional field
                )
                leads.append(lead)
            except KeyError as e: # Should be caught by missing_fields check, but as a safeguard
                logger.warning(f"Skipping lead due to missing key {e} in {filepath}: {lead_data.get('id', 'N/A')}")
            except TypeError as e: # If lead_data is not a dict as expected by Lead constructor
                 logger.warning(f"Skipping lead due to TypeError ({e}) in {filepath}: {lead_data.get('id', 'N/A')}")

        logger.info(f"Successfully loaded {len(leads)} leads from {filepath}.")
        return leads

    except FileNotFoundError:
        logger.error(f"Lead file not found: {filepath}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {filepath}: {e}")
        raise ValueError(f"Invalid JSON format in {filepath}: {e}")
    except Exception as e: # Catch any other unexpected errors during loading
        logger.error(f"An unexpected error occurred while loading leads from {filepath}: {e}")
        raise


def get_lead_by_id(lead_id: str, leads_list: Optional[List[Lead]] = None) -> Optional[Lead]:
    """
    Retrieves a specific lead by their ID.

    Args:
        lead_id: The ID of the lead to retrieve.
        leads_list: An optional list of leads to search within.
                    If None, leads will be loaded from the default filepath.

    Returns:
        The Lead object if found, otherwise None.
    """
    if leads_list is None:
        try:
            leads_list = load_leads()
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Could not load leads to search for lead ID {lead_id}: {e}")
            return None # Or re-raise, depending on desired behavior

    for lead in leads_list:
        if lead.id == lead_id:
            return lead

    logger.debug(f"Lead with ID '{lead_id}' not found.")
    return None

if __name__ == '__main__':
    # Example Usage:
    logging.basicConfig(level=logging.INFO)

    # Test loading leads
    try:
        all_leads = load_leads()
        if all_leads:
            logger.info(f"First lead loaded: {all_leads[0]}")
    except Exception as e:
        logger.error(f"Error in load_leads example: {e}")

    # Test getting a specific lead
    if all_leads:
        test_lead_id = "lead_001"
        specific_lead = get_lead_by_id(test_lead_id, all_leads)
        if specific_lead:
            logger.info(f"Found lead by ID '{test_lead_id}': {specific_lead}")
        else:
            logger.warning(f"Lead with ID '{test_lead_id}' not found.")

        test_non_existent_id = "lead_999"
        specific_lead_none = get_lead_by_id(test_non_existent_id, all_leads)
        if specific_lead_none is None:
            logger.info(f"Correctly did not find lead with ID '{test_non_existent_id}'.")
        else:
            logger.error(f"Incorrectly found a lead for non-existent ID '{test_non_existent_id}'.")

    # Test with a non-existent file
    try:
        load_leads("data/non_existent_leads.json")
    except FileNotFoundError:
        logger.info("Correctly caught FileNotFoundError for non_existent_leads.json")
    except Exception as e:
        logger.error(f"Unexpected error when testing non-existent file: {e}")

    # Test with a malformed JSON (requires creating such a file manually or mocking)
    # For now, this part is conceptual unless we create a malformed file for testing.
    # with open("data/malformed.json", "w") as f:
    #     f.write("[{'id': 'bad'}]") # Invalid JSON (single quotes)
    # try:
    #     load_leads("data/malformed.json")
    # except ValueError as e:
    #     logger.info(f"Correctly caught ValueError for malformed JSON: {e}")
    # finally:
    #     if os.path.exists("data/malformed.json"):
    #         os.remove("data/malformed.json")
