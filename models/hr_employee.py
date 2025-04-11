from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import ValidationError
import requests
import csv
from io import StringIO
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    swedish_personnummer = fields.Char(string='Personal Identity Number', help='Swedish Personal Identity Number')
    region_id = fields.Many2one('res.region', string='Region')
    municipality_id = fields.Many2one('res.municipality', string='Municipality', domain="[('region_id', '=', region_id)]")
    church_member = fields.Boolean(string='Church Member', default=False)
    parish_id = fields.Many2one('res.parish', string='Parish', domain="[('municipality_id', '=', municipality_id)]")
    tax_table_number = fields.Char(related='municipality_id.tax_table_number', string='Tax Table Number', readonly=True)

    @api.onchange('municipality_id')
    def _onchange_municipality_id(self):
        if self.municipality_id:
            self.parish_id = False  # Reset parish if municipality changes

    @api.model
    def ensure_municipality_data_loaded(self):
        _logger.debug("Ensuring municipality data is loaded.")
        Region = self.env['res.region']
        Municipality = self.env['res.municipality']
        
        if not Region.search([], limit=1) or not Municipality.search([], limit=1):
            _logger.info("Municipality data not found, updating municipalities.")
            self.env['municipality.updater'].update_municipalities()
        else:
            _logger.debug("Municipality data is already loaded.")

    @api.model
    def default_get(self, fields_list):
        self.ensure_municipality_data_loaded()
        return super(HrEmployee, self).default_get(fields_list)

    @api.onchange('swedish_personnummer')
    def _onchange_swedish_personnummer(self):
        if self.swedish_personnummer:
            digits_only = ''.join(filter(str.isdigit, self.swedish_personnummer))

            if len(digits_only) == 12:
                luhn_digits = digits_only[2:]
            elif len(digits_only) == 10:
                luhn_digits = digits_only
            else:
                self.swedish_personnummer = ''
                return {
                    'warning': {
                        'title': 'Invalid format',
                        'message': 'The personal identity number must contain 10 or 12 digits.'
                    }
                }

            if not self._luhn_check(luhn_digits):
                self.swedish_personnummer = ''
                return {
                    'warning': {
                        'title': 'Invalid personal identity number',
                        'message': 'The personal identity number failed the Luhn algorithm check.'
                    }
                }

            formatted_personnummer = self._format_personnummer(digits_only)
            if formatted_personnummer:
                self.swedish_personnummer = formatted_personnummer
            else:
                self.swedish_personnummer = ''
                return {
                    'warning': {
                        'title': 'Invalid date or age',
                        'message': 'The personal identity number contains an invalid date or the age is outside the allowed range (15-75 years).'
                    }
                }

    @api.constrains('swedish_personnummer')
    def _check_personnummer(self):
        for employee in self:
            if employee.swedish_personnummer:
                digits_only = ''.join(filter(str.isdigit, employee.swedish_personnummer))
                if len(digits_only) == 12:
                    luhn_digits = digits_only[2:]
                else:
                    luhn_digits = digits_only

                if not self._luhn_check(luhn_digits):
                    raise ValidationError("Invalid Swedish personal identity number.")

    def _format_personnummer(self, digits):
        if len(digits) == 12:
            year, month, day, extension = digits[:4], digits[4:6], digits[6:8], digits[8:]
        elif len(digits) == 10:
            year, month, day, extension = '19' + digits[:2], digits[2:4], digits[4:6], digits[6:]
        else:
            return None

        try:
            birth_date = datetime.strptime(f"{year}{month}{day}", "%Y%m%d")
        except ValueError:
            return None

        age = (datetime.now() - birth_date).days / 365.25
        if age < 15 or age > 75:
            return None

        return f"{year}{month}{day}-{extension}"

    def _luhn_check(self, digits):
        digits = [int(d) for d in digits]
        checksum = 0
        for idx, digit in enumerate(digits[:-1]):
            if idx % 2 == 0:
                prod = digit * 2
                checksum += prod if prod < 10 else prod - 9
            else:
                checksum += digit
        control_digit = (10 - (checksum % 10)) % 10
        return control_digit == digits[-1]


class ResMunicipality(models.Model):
    _name = 'res.municipality'
    _description = 'Swedish Municipality'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    region_id = fields.Many2one('res.region', string='Region', required=True)
    tax_table_number = fields.Char(required=True)
    total_tax_rate = fields.Float(string='Total Tax Rate', required=True)
    church_tax_rate = fields.Float(string='Church Tax Rate', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Municipality code must be unique.')
    ]


class ResRegion(models.Model):
    _name = 'res.region'
    _description = 'Swedish Region'

    name = fields.Char(required=True)
    municipality_ids = fields.One2many('res.municipality', 'region_id', string='Municipalities')


class ResParish(models.Model):
    _name = 'res.parish'
    _description = 'Swedish Parish'

    name = fields.Char(required=True)
    municipality_id = fields.Many2one('res.municipality', string='Municipality', required=True)


class MunicipalityUpdater(models.Model):
    _name = 'municipality.updater'
    _description = 'Municipality Updater'

    @api.model
    def update_municipalities(self):
        _logger.info("Starting the municipality update process.")

        Region = self.env['res.region']
        Municipality = self.env['res.municipality']

        scb_url = 'https://skatteverket.entryscape.net/rowstore/dataset/c67b320b-ffee-4876-b073-dd9236cd2a99/json'

        response = requests.get(scb_url)
        response.raise_for_status()
        data = response.json()

        for region in data['regioner']:
            region_code = region['regionkod']
            region_name = region['regionnamn']
            region_rec = Region.search([('code', '=', region_code)], limit=1)
            if not region_rec:
                region_rec = Region.create({
                    'name': region_name,
                    'code': region_code
                })

            for municipality in region['kommuner']:
                municipality_code = municipality['kommunkod']
                municipality_name = municipality['kommunnamn']

                municipality_rec = Municipality.search([('code', '=', municipality_code)], limit=1)
                if not municipality_rec:
                    Municipality.create({
                        'name': municipality_name,
                        'code': municipality_code,
                        'region_id': region_rec.id,
                        'tax_table_number': '',
                        'total_tax_rate': 0.0,
                        'church_tax_rate': 0.0,
                    })

        _logger.info("Regions and municipalities loaded from SCB.")

        # Now you can fetch tax data from the Tax Agency and update the municipalities
        skatt_url = 'https://skatteverket.entryscape.net/rowstore/dataset/c67b320b-ffee-4876-b073-dd9236cd2a99/json'
        resp_skatt = requests.get(skatt_url)
        resp_skatt.raise_for_status()
        skatt_data = resp_skatt.json().get('results', [])

        for mun in skatt_data:
            municipality_name = mun['kommun']
            municipality = Municipality.search([('name', '=', municipality_name)], limit=1)

            if not municipality:
                _logger.warning(f"Municipality not found: {municipality_name}")
                continue

            data = {
                'tax_table_number': mun['år'],
                'total_tax_rate': float(mun['summa, exkl. kyrkoavgift'].replace(',', '.')),
                'church_tax_rate': float(mun['kyrkoavgift'].replace(',', '.')) + float(mun.get('begravnings-avgift', '0').replace(',', '.')),
            }
            municipality.write(data)

        _logger.info("Municipality update process completed.")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_update_regions_municipalities(self):
        self.env['municipality.updater'].update_municipalities()