from odoo import models, fields, api

class ResParish(models.Model):
    _name = 'res.parish'
    _description = 'Swedish Parish'

    name = fields.Char(required=True)
    municipality_id = fields.Many2one('res.municipality', string='Municipality', required=True)