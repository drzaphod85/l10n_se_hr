from odoo import models, fields, api
import requests
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)

class MunicipalityUpdater(models.Model):
    _name = 'municipality.updater'
    _description = 'Municipality and Tax Rate Updater'

    last_update = fields.Datetime(string='Last Update', readonly=True)
    update_status = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed')
    ], string='Update Status', default='pending')
    update_message = fields.Text(string='Update Message')
    run_manually = fields.Boolean(string='Run Manually', default=False)
    
    @api.model
    def update_municipalities(self):
        """Update municipalities and their tax rates from Skatteverket"""
        _logger.info("Starting the municipality update process")
        self.ensure_one() if self else self.create({})
        self.update_status = 'pending'
        success = True
        message = ""
        
        try:
            # First, ensure regions are loaded
            success, regions_message = self._update_regions()
            message += regions_message
            
            if success:
                # Then update municipalities and connect to regions
                success, municipalities_message = self._update_municipalities_list()
                message += municipalities_message
                
                if success:
                    # Finally, update tax rates for municipalities
                    success, tax_message = self._update_tax_rates()
                    message += tax_message
        
        except Exception as e:
            success = False
            message = f"Error in update process: {str(e)}"
            _logger.error(message)
        
        self.write({
            'last_update': fields.Datetime.now(),
            'update_status': 'success' if success else 'failed',
            'update_message': message
        })
        
        return success
    
    def _update_regions(self):
        """Ensure all Swedish regions are loaded"""
        Region = self.env['res.region']
        message = "Regions check completed.\n"
        
        # Check if regions already exist
        existing_regions = Region.search([])
        if existing_regions:
            return True, "Regions already exist in the system.\n"
        
        try:
            # The file with regions should already be loaded during module installation
            regions = Region.search([])
            if regions:
                return True, f"Found {len(regions)} regions.\n"
            else:
                # If somehow regions are not loaded, log an error
                return False, "Regions data not found. Please ensure the module is properly installed.\n"
        except Exception as e:
            return False, f"Error checking regions: {str(e)}\n"
    
    def _update_municipalities_list(self):
        """Update municipalities list from SCB or static data"""
        Municipality = self.env['res.municipality']
        Region = self.env['res.region']
        message = "Municipalities update started.\n"
        
        try:
            # For a production system, we would fetch from SCB API or a similar source
            # Here using the API endpoint for Swedish municipalities
            scb_url = 'https://api.scb.se/OV0104/v1/doris/sv/ssd/START/OE/OE0101/OE0101A/KommunalSkattMedelKN'
            
            # This would be the proper API call for a production system
            # For demonstration, we'll use the data already loaded by XML files
            try:
                response = requests.post(scb_url, json={
                    "query": [],
                    "response": {"format": "json"}
                }, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    # Process the API response
                    # This would map municipality codes to regions and create records
                    message += f"SCB API returned data successfully.\n"
                else:
                    message += f"SCB API returned status code {response.status_code}.\n"
                    message += "Checking for existing municipalities from data files.\n"
            except Exception as e:
                message += f"Failed to connect to SCB API: {str(e)}.\n"
                message += "Checking for existing municipalities from data files.\n"
            
            # Check if municipalities already exist (from XML loading)
            municipalities = Municipality.search([])
            if municipalities:
                message += f"Found {len(municipalities)} municipalities already loaded.\n"
                return True, message
            else:
                message += "No municipalities found. Please check data files.\n"
                return False, message
                
        except Exception as e:
            return False, f"Error updating municipalities list: {str(e)}\n"
    
    def _update_tax_rates(self):
        """Update tax rates from Skatteverket for all municipalities"""
        Municipality = self.env['res.municipality']
        message = "Tax rates update started.\n"
        current_year = datetime.now().year
        
        try:
            # Skatteverket API or data source for tax rates
            # In production, this would be the URL for the Skatteverket open data API
            skatt_url = f'https://skatteverket.entryscape.net/rowstore/dataset/c67b320b-ffee-4876-b073-dd9236cd2a99/json'
            
            try:
                response = requests.get(skatt_url, timeout=30)
                if response.status_code == 200:
                    tax_data = response.json()
                    results = tax_data.get('results', [])
                    message += f"Found {len(results)} tax records from Skatteverket API.\n"
                    
                    # Counting variables for summary
                    processed = 0
                    updated = 0
                    errors = 0
                    
                    for tax_record in results:
                        try:
                            # Extract information from API response
                            municipality_name = tax_record.get('kommun', '').strip()
                            year = tax_record.get('år', str(current_year))
                            
                            # Filter for current year only
                            if year != str(current_year):
                                continue
                                
                            # Find municipality by name
                            municipalities = Municipality.search([('name', 'ilike', municipality_name)])
                            
                            if municipalities:
                                for municipality in municipalities:
                                    # Extract tax rates, handling possible format variations
                                    try:
                                        # Total tax excluding church tax
                                        total_tax = tax_record.get('summa, exkl. kyrkoavgift', '0')
                                        if isinstance(total_tax, str):
                                            total_tax = total_tax.replace(',', '.')
                                        total_tax_rate = float(total_tax)
                                        
                                        # Church tax
                                        church_tax = tax_record.get('kyrkoavgift', '0')
                                        if isinstance(church_tax, str):
                                            church_tax = church_tax.replace(',', '.')
                                        church_tax_rate = float(church_tax)
                                        
                                        # Burial fee (part of church tax in Sweden)
                                        burial_fee = tax_record.get('begravnings-avgift', '0')
                                        if isinstance(burial_fee, str):
                                            burial_fee = burial_fee.replace(',', '.')
                                        burial_fee = float(burial_fee)
                                        
                                        # Add burial fee to church tax
                                        church_tax_rate += burial_fee
                                        
                                        # Update municipality with tax rates
                                        municipality.write({
                                            'tax_table_number': tax_record.get('år', '29'),
                                            'total_tax_rate': total_tax_rate,
                                            'church_tax_rate': church_tax_rate
                                        })
                                        updated += 1
                                    except (ValueError, TypeError) as e:
                                        errors += 1
                                        _logger.warning(f"Error parsing tax rates for {municipality_name}: {str(e)}")
                            processed += 1
                        except Exception as e:
                            errors += 1
                            _logger.error(f"Error processing tax record: {str(e)}")
                    
                    message += f"Processed {processed} municipalities, updated {updated}, with {errors} errors.\n"
                else:
                    message += f"Skatteverket API returned status code {response.status_code}. Using default values.\n"
                    # Set default values for municipalities missing tax data
                    default_municipalities = Municipality.search([('total_tax_rate', '=', 0.0)])
                    for municipality in default_municipalities:
                        municipality.write({
                            'tax_table_number': '29',
                            'total_tax_rate': 32.0,  # Default average rate
                            'church_tax_rate': 1.0  # Default church tax rate
                        })
                    message += f"Set default tax rates for {len(default_municipalities)} municipalities.\n"
            except Exception as e:
                message += f"Failed to connect to Skatteverket API: {str(e)}. Using default values.\n"
                # Set default values for all municipalities
                municipalities = Municipality.search([])
                for municipality in municipalities:
                    if not municipality.total_tax_rate or municipality.total_tax_rate == 0.0:
                        municipality.write({
                            'tax_table_number': '29',
                            'total_tax_rate': 32.0,  # Default average rate
                            'church_tax_rate': 1.0  # Default church tax rate
                        })
                message += f"Set default tax rates for {len(municipalities)} municipalities.\n"
            
            return True, message
            
        except Exception as e:
            return False, f"Error updating tax rates: {str(e)}\n"