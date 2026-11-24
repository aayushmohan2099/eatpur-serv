from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0011_alter_coupon_coupon_type_alter_coupon_discount_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="saleorder",
            name="applied_coupons",
            field=models.ManyToManyField(
                blank=True,
                related_name="sale_orders",
                to="shop.coupon",
                verbose_name="Applied Coupons",
            ),
        ),
    ]
