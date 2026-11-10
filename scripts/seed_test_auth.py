import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()


def seed():
    from partner.models import BadmintonCenter
    from users.models import PartnerProfile, User

    print("Đang tạo tài khoản test phân quyền...")

    partner, _ = User.objects.get_or_create(
        username='doitac_test',
        email='doitac@test.com',
        defaults={'role': 'partner'},
    )
    partner.set_password('123456')
    partner.save()

    partner_profile, _ = PartnerProfile.objects.get_or_create(user=partner)

    center1, _ = BadmintonCenter.objects.get_or_create(
        name='Chi Nhánh Hà Nội',
        partner=partner_profile,
        defaults={'address': 'Cầu Giấy, HN'},
    )
    center2, _ = BadmintonCenter.objects.get_or_create(
        name='Chi Nhánh Hồ Chí Minh',
        partner=partner_profile,
        defaults={'address': 'Quận 1, HCM'},
    )

    staff, _ = User.objects.get_or_create(
        username='nhanvien_test',
        email='nhanvien@test.com',
        defaults={'role': 'staff'},
    )
    staff.set_password('123456')
    staff.save()

    staff_profile = staff.staff_profile
    staff_profile.center = center1
    staff_profile.save()

    print(f"Partner: doitac_test -> {center1.name}, {center2.name}")
    print(f"Staff: nhanvien_test -> {center1.name}")


if __name__ == '__main__':
    seed()
