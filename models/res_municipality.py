from odoo import models, fields, api

class ResMunicipality(models.Model):
    _name = 'res.municipality'
    _description = 'Swedish Municipality'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    region_id = fields.Many2one('res.region', string='Region', required=True)
    tax_table_number = fields.Char(required=True)
    total_tax_rate = fields.Float(string='Total Tax Rate', required=False)
    church_tax_rate = fields.Float(string='Church Tax Rate', required=False)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Municipality code must be unique.')
    ]