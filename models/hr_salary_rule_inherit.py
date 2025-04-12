from odoo import models, fields, api

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    
    is_swedish_specific = fields.Boolean(string='Swedish Specific Rule')
    applies_church_tax = fields.Boolean(string='Applies Church Tax')
