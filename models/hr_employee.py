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