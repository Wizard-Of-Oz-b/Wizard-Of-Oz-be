from django.db import migrations

def forwards(apps, schema_editor):
    Admin = apps.get_model("staff", "Admin")
    Admin.objects.filter(role="super").update(role="admin")

def backwards(apps, schema_editor):
    Admin = apps.get_model("staff", "Admin")
    Admin.objects.filter(role="admin").update(role="super")

class Migration(migrations.Migration):
    dependencies = [
        ("staff", "0001_initial"),  # ← 바로 직전 파일을 의존성으로
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
