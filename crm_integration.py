
import os
import requests
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_lead_to_hubspot(lead, api_key):
    """
    Add a lead to HubSpot CRM
    """
    try:
        url = 'https://api.hubapi.com/crm/v3/objects/contacts'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        
        # Determine pipeline based on lead score
        pipeline = 'opportunity' if lead.score > 75 else 'lead'
        
        # Parse name for first/last name
        name_parts = lead.name.split() if ' ' in lead.name else [lead.name, '']
        first_name = name_parts[0]
        last_name = name_parts[-1] if len(name_parts) > 1 else ''
        
        # Prepare data for HubSpot
        data = {
            'properties': {
                'email': lead.email,
                'firstname': first_name,
                'lastname': last_name,
                'phone': getattr(lead, 'phone', ''),
                'linkedin_url': getattr(lead, 'linkedin_url', ''),
                'leadzap_score': str(lead.score),
                'leadzap_source': lead.source,
                'lifecyclestage': pipeline
            }
        }
        
        # Send request to HubSpot
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 201:
            crm_id = response.json().get('id')
            logger.info(f"Added lead {lead.name} to HubSpot with ID {crm_id}")
            return crm_id
        else:
            logger.error(f"Failed to add lead to HubSpot: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error adding lead to HubSpot: {str(e)}")
        return None

def update_lead_status(lead, status, api_key):
    """
    Update lead status in HubSpot CRM
    """
    if not lead.crm_id:
        logger.warning(f"Cannot update lead {lead.name} status - no CRM ID")
        return False
    
    try:
        url = f'https://api.hubapi.com/crm/v3/objects/contacts/{lead.crm_id}'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        
        data = {
            'properties': {
                'lifecyclestage': status.lower(),
                'leadzap_status': status
            }
        }
        
        response = requests.patch(url, json=data, headers=headers)
        if response.status_code == 200:
            logger.info(f"Updated lead {lead.name} status to {status} in HubSpot")
            return True
        else:
            logger.error(f"Failed to update lead status in HubSpot: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error updating lead status in HubSpot: {str(e)}")
        return False

def notify_slack(lead, webhook_url):
    """
    Send a notification to Slack about a new lead
    """
    try:
        # Determine lead quality based on score
        lead_quality = 'Hot Lead 🔥' if lead.score > 75 else 'Warm Lead 👍'
        
        # Create message with lead details
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"New {lead_quality} Added",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Name:*\n{lead.name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Score:*\n{lead.score}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Email:*\n{lead.email}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Source:*\n{lead.source}"
                        }
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Added to CRM at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} via Leadzap"
                        }
                    ]
                }
            ]
        }
        
        # Add phone and LinkedIn URL if available
        if hasattr(lead, 'phone') and lead.phone:
            message["blocks"][1]["fields"].append({
                "type": "mrkdwn",
                "text": f"*Phone:*\n{lead.phone}"
            })
            
        if hasattr(lead, 'linkedin_url') and lead.linkedin_url:
            message["blocks"][1]["fields"].append({
                "type": "mrkdwn",
                "text": f"*LinkedIn:*\n{lead.linkedin_url}"
            })
        
        # Send notification to Slack
        response = requests.post(webhook_url, json=message)
        
        if response.status_code == 200:
            logger.info(f"Sent Slack notification for lead {lead.name}")
            return True
        else:
            logger.error(f"Failed to send Slack notification: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Slack notification: {str(e)}")
        return False
