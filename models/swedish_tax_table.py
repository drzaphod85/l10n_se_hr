from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SwedishTaxTable(models.Model):
    _name = 'hr.swedish.tax.table'
    _description = 'Swedish Tax Table'
    
    name = fields.Char(string='Name', required=True)
    table_number = fields.Char(string='Table Number', required=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    table_type = fields.Selection([
        ('table_29', 'Table 29 - Monthly salary'),
        ('table_30', 'Table 30 - Weekly salary'),
        ('table_31', 'Table 31 - Daily salary')
    ], string='Table Type', required=True)
    column_ids = fields.One2many('hr.swedish.tax.table.column', 'table_id', string='Columns')
    
    _sql_constraints = [
        ('table_year_unique', 'unique(table_number, year)', 'Tax table must be unique per year.')
    ]
    
    @api.model
    def import_tax_tables(self):
        """Import tax tables from Skatteverket"""
        # This would fetch and parse tax tables from Skatteverket
        # Implementation depends on available APIs or files
        pass


class SwedishTaxTableColumn(models.Model):
    _name = 'hr.swedish.tax.table.column'
    _description = 'Swedish Tax Table Column'
    
    name = fields.Char(string='Name', required=True)
    column_number = fields.Integer(string='Column Number', required=True)
    table_id = fields.Many2one('hr.swedish.tax.table', string='Tax Table', required=True, ondelete='cascade')
    bracket_ids = fields.One2many('hr.swedish.tax.bracket', 'column_id', string='Tax Brackets')


class SwedishTaxBracket(models.Model):
    _name = 'hr.swedish.tax.bracket'
    _description = 'Swedish Tax Bracket'
    _order = 'lower_limit'
    
    column_id = fields.Many2one('hr.swedish.tax.table.column', string='Table Column', required=True, ondelete='cascade')
    lower_limit = fields.Float(string='Lower Income Limit', required=True)
    upper_limit = fields.Float(string='Upper Income Limit', required=True)
    tax_amount = fields.Float(string='Tax Amount', required=True, help='Fixed amount or percentage depending on table type')
    is_percentage = fields.Boolean(string='Is Percentage', default=False)
    
    @api.constrains('lower_limit', 'upper_limit')
    def _check_limits(self):
        for bracket in self:
            if bracket.lower_limit >= bracket.upper_limit:
                raise ValidationError("Upper limit must be greater than lower limit.")