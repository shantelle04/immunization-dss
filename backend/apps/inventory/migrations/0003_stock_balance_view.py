from django.db import migrations

CREATE = """
CREATE VIEW inventory_stock_balance AS
SELECT facility_id, antigen_id, SUM(quantity_doses)::integer AS balance
FROM inventory_stocktransaction
GROUP BY facility_id, antigen_id
"""


class Migration(migrations.Migration):
    dependencies = [("inventory", "0002_initial")]

    operations = [migrations.RunSQL(CREATE, reverse_sql="DROP VIEW inventory_stock_balance")]
