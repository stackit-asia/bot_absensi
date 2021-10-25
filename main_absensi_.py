from typing import Optional, Tuple, Union, List
from rich.console import Console
from twilio.rest import Client
from pathlib import Path
from lxml import html
import configparser
import threading
import openpyxl
import requests
import datetime
import time
import os
import re
import sys


class Notifikasi:
    def WA(
        self,
        pesan: str,
        nomer_hp: str,
    ):
        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        client = Client(account_sid, auth_token)

        message = client.messages.create(
            from_="whatsapp:+14155238886",
            body=pesan,
            to=f"whatsapp:{nomer_hp}",
        )
        # print(message.sid)


class Elearning(Notifikasi):
    URL_LOGIN = "https://e-learning.asia.ac.id/login/index.php"
    URL_HALAMAN_UTAMA = "https://e-learning.asia.ac.id/my"

    session = requests.session()
    headers = {
        "Host": "e-learning.asia.ac.id",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://e-learning.asia.ac.id",
        "Alt-Used": "e-learning.asia.ac.id",
        "Connection": "keep-alive",
    }

    def __init__(self, nim: str, password: str, nomer_hp: str):
        self.nim = nim
        self.password = password
        self.nomer_hp = nomer_hp
        self.checkout_kehadiran = ["Present", "Hadir"]

    def notifikasi(self, pesan: str, nomer_hp: str) -> None:
        super().WA(pesan, nomer_hp)

    @property
    def ambil_nama_hari(self) -> datetime:
        return datetime.datetime.today().strftime("%A")

    @property
    def ambil_waktu_sekarang(self) -> datetime:
        return datetime.datetime.today().strftime("%d/%m/%Y, %H:%M:%S")

    @property
    def format_waktu(self) -> str:
        hari_sekarang = self.ambil_nama_hari
        waktu_sekarang = self.ambil_waktu_sekarang
        return f"{hari_sekarang} {waktu_sekarang}"

    def login(self):
        """Method digunakan untuk melakukan login pada e-learning.

        payload = {
            "username": self.nim,
            "password": self.password,
            "logintoken": "",
        }
        nilai "logintoken" akan di isi setelah mendapatkan hasil response dari URL login e-learning "logintoken" berupa nilai CRSF token.
        """

        response = self.session.get(self.URL_LOGIN)
        source = html.fromstring(response.text)

        payload = {
            "username": self.nim,
            "password": self.password,
            "logintoken": "",
        }

        payload["logintoken"] = list((set(source.xpath("//input[@name='logintoken']/@value"))))[0]

        response = self.session.post(self.URL_LOGIN, data=payload, headers=dict(referer=self.URL_LOGIN))

        if response.status_code == 200:
            status_login, nama_pemilik_akun = self.ambil_nama_pemilik_akun()

            if status_login:
                pesan = f"Selamat datang *{nama_pemilik_akun}*, kamu berhasil login di e-learning.\nPada *{self.format_waktu}*"
                self.notifikasi(pesan, nomer_hp=self.nomer_hp)
                return self.session
            else:
                pesan = "Maaf kamu belum berhasil login di e-learning, pastikan NIM dan password sudah benar"
                self.notifikasi(pesan, nomer_hp=self.nomer_hp)
                exit(pesan)

    def ambil_nama_pemilik_akun(self) -> Tuple[bool, str]:
        """Method untuk melakukan pencarian nama pemilik akun e-learning, setelah berhasil melakukan login di e-learning.

        Returns:
            Tuple[bool, str]: Tuple[status_login, nama_pemilik_akun]
        """
        response = self.session.get(self.URL_HALAMAN_UTAMA)
        source = html.fromstring(response.text)

        nama_pemilik_akun = source.xpath('//header[@id="page-header"]//div[@class="page-header-headings"]/h1/text()')

        if len(nama_pemilik_akun) != 0:
            print("=== Login Berhasil ===")
            return True, nama_pemilik_akun[0].title()
        else:
            print("=== Login Gagal ===")
            return False, nama_pemilik_akun

    def ambil_nama_matkul(self, url_matkul: str) -> Union[str, bool]:
        """Method untuk mengambil nama matkul yg aktif atau sedang di akses sekarang.

        Args:
            url_matkul (str): url mata kuliah yg akan di akses

        Returns:
            Union[str, bool]: return mata kuliah jika ditemuan else False
        """
        response = self.session.get(url_matkul)
        source = html.fromstring(response.text)
        nama_matkul = source.xpath('//div[@class="page-header-headings"]/h1/text()')
        return nama_matkul[0] if len(nama_matkul) != 0 else False

    def print_matkul(self, url_matkul: str) -> str:
        matkul = self.ambil_nama_matkul(url_matkul)

        if bool(matkul):
            pesan = f"Kamu aktif di mata kuliah *{matkul}*.\n\nMencoba mencari link untuk absensi..."
            return pesan
        else:
            exit("Nama matkul tidak ditemukan")

    def ambil_link_absensi(self, url_matkul: str, nama_matkul: str = None, password: str = None) -> list:
        """Method untuk mengakses halaman matkul kemudian juga akan mencari,
        semua link absensi, jika link ditemukan makan akan dilakukan pencarian lagi  untuk mencari link yg aktif untuk melakukan absensi hari ini."""

        pesan_dihalaman_matkul_sekarang = self.print_matkul(url_matkul)
        response = self.session.get(url_matkul)
        source = html.fromstring(response.text)

        # format xpath mencari tag li atau pembungkus bagian absensi di tiap pertemuan
        xpath_mencari_semua_tag_li = '//ul[@class="topics"]/li'

        for element in source.xpath(xpath_mencari_semua_tag_li):
            attrb_id_judul = element.attrib["aria-labelledby"]
            judul_pertemuan = element.xpath(f'//*[@id="{attrb_id_judul}"]//a/text()')[0]

            # mencari tag li yg memiliki class activity attendance modtype_attendance, kemudian mencari tag a dan mengambil nilai href
            list_link_tiap_pertemuan = element.xpath('.//ul[@class="section img-text"]/li[@class="activity attendance modtype_attendance "]//a/@href')
            if len(list_link_tiap_pertemuan) != 0:
                # print(judul_pertemuan)
                link_absensi = list_link_tiap_pertemuan[0]
                response_status = self.ambil_url_submit_attendance(link_absensi, pesan_dihalaman_matkul_sekarang, password)
                if response_status == False:
                    self.ambil_url_submit_attendance_di_background(link_absensi, nama_matkul=nama_matkul, password_absen=password)

    def ambil_url_submit_attendance(self, url_absen: str, pesan: str = None, password_absen: str = None) -> bool:
        """Method untuk mencari kata submit attendance pada halaman absensi, jika kata yg di cari ditemukan maka return url submit_attendance"""

        response = self.session.get(url_absen)
        source = html.fromstring(response.text)

        list_url_submit = source.xpath('//*[text()="Submit attendance"]//parent::a/@href')
        if len(list_url_submit) != 0:
            pesan = f"{pesan}\n\nUrl absensi ditemukan, mencoba mencari metode absensi..."
            self.ambil_metode_absensi(pesan, list_url_submit, password_absen)
        else:
            if pesan is not None:
                pesan = f"{pesan}\n\nUrl absensi tidak ditemukan"
                self.notifikasi(pesan, nomer_hp=self.nomer_hp)
            return False

    def ambil_url_submit_attendance_di_background(
        self,
        url_absen: str,
        nama_matkul: str = None,
        pesan: str = None,
        password_absen: str = None,
    ):
        """Method untuk mencari link absensi yg harus nya sudah aktif pada jam yg sudah
        ditentukan oleh dosen, jika link tedapat ketelambatan muncul di halaman maka
        method ini akan terus berjalan di latar belakang sampai link absensi ditemukan


        Args:
            url_absen (str): url absensi
            nama_matkul (str, optional): nama mata kuliah. Defaults to None.
            pesan (str, optional): pesan yang akan dikirim. Defaults to None.
            password_absen (str, optional): password untuk absen. Defaults to None.
        """
        berhasil_absen = False
        console = Console()
        while not berhasil_absen:
            status_absen = self.ambil_url_submit_attendance(url_absen, password_absen=password_absen)
            console.log(f"[red]Daemon, mencari absensi {nama_matkul}")
            time.sleep(5)

            if status_absen:
                berhasil_absen = True

    def ambil_metode_absensi(self, pesan: str, url_submit_absensi: list, password_absen: str = None) -> None:
        for url_submit in url_submit_absensi:
            sessid, sesskey = re.findall(fr"sessid=(.+)&sesskey=(.+)", url_submit)[0]
            response = self.session.get(url_submit)
            source = html.fromstring(response.text)

            is_absensi_dengan_password = source.xpath('//*[@id="id_studentpassword"]')

            # mengambil nilai checkout kehadiran
            for label_kehadiran in self.checkout_kehadiran:
                status_kehadiran = source.xpath(f'//label//span[text()="{label_kehadiran}"]//preceding::input[1]/@value')
                if len(status_kehadiran) != 0:
                    status_kehadiran = status_kehadiran[0]
                else:
                    exit(f"Checkout status kehadiran tidak ditemukan diantara{' '.join(self.checkout_kehadiran)}")

            if len(is_absensi_dengan_password) != 0:
                pesan = f"{pesan}\n\nAbsensi menggunakan password,mencoba absensi menggunakan password yang tersedia...\n\nHoraa... kamu telah berhasil melakukan absensi!"
                self.notifikasi(pesan, nomer_hp=self.nomer_hp)
                self.absensi_dengan_password(url_submit, password_absen, sessid, sesskey, status_kehadiran)
            else:
                pesan = f"{pesan}\n\nMencoba absensi..\n\nHoraa... kamu telah berhasil melakukan absensi!"
                self.notifikasi(pesan, nomer_hp=self.nomer_hp)
                self.absensi_tanpa_password(url_submit, sessid, sesskey, status_kehadiran)

    def absensi_dengan_password(
        self,
        url_submit: str,
        password_absen: str,
        sessid: str,
        sesskey: str,
        status_kehadiran: str,
    ) -> None:
        payload = [
            ("sessid", sessid),
            ("sesskey", sesskey),
            ("sesskey", sesskey),
            ("studentpassword", password_absen),
            ("_qf__mod_attendance_student_attendance_form", "1"),
            ("mform_isexpanded_id_session", "1"),
            ("status", status_kehadiran),
            ("submitbutton", "Save changes"),
        ]
        self.session.post(url_submit, headers=self.headers, data=payload)

    def absensi_tanpa_password(self, url_submit, sessid, sesskey, status_kehadiran) -> None:
        payload = [
            ("sessid", sessid),
            ("sesskey", sesskey),
            ("sesskey", sesskey),
            ("_qf__mod_attendance_student_attendance_form", "1"),
            ("mform_isexpanded_id_session", "1"),
            ("status", status_kehadiran),
            ("submitbutton", "Save changes"),
        ]
        self.session.post(url_submit, headers=self.headers, data=payload)


class BacaJadwal(Elearning):
    def __init__(self, path_file_jadwal: Union[Path, str] = None):
        self.path_jadwal = path_file_jadwal
        self.ws = self.ambil_worksheet

    @property
    def ambil_worksheet(self) -> openpyxl:
        if self.path_jadwal is not None:
            wb = openpyxl.load_workbook(filename=self.path_jadwal, read_only=True)
            ws = wb.active
            return ws
        else:
            exit("File jadwal belum ditentukan!")

    def ambil_data_cell(self, start_kolom: str, end_kolom: str) -> Tuple[List[list], list]:
        list_data = list()

        for row in range(3, 13):
            data_cell = self.ws[f"{start_kolom}{row}":f"{end_kolom}{row}"]
            jam, link, password = data_cell[0]

            if jam.value is not None:
                list_matkul = (
                    str(jam.value),
                    str(link.value),
                    str(password.value),
                )
                list_data.append(list(list_matkul))

        list_nama_matkul = self.ambil_matkul_hari_ini(list_data)
        return list_data, list_nama_matkul

    def ambil_nama_matkul(self, url_matkul: str) -> Union[str, bool]:
        return super().ambil_nama_matkul(url_matkul)

    def ambil_matkul_hari_ini(self, list_matkul: List[list]) -> list:
        list_url_matkul = [data[1] for data in list_matkul]
        return list(map(self.ambil_nama_matkul, list_url_matkul))


# class Alarm(Elearning):
#     def __init__(self, nim: str, password: str, nomer_hp: str):
#         super().__init__(nim, password, nomer_hp)

#     def ambil_link_absensi(
#         self, url_matkul: str, nama_matkul: str, password: str = None
#     ) -> list:
#         return super().ambil_link_absensi(url_matkul, nama_matkul, password=password)

#     def set_alarm(
#         self,
#         nama_matkul: str,
#         url_matkul: str,
#         password_matkul: str,
#         tgt_jam: Union[str, datetime.date] = None,
#     ):
#         set_alarm = str(tgt_jam)
#         waktu_sekarang = time.strftime("%H:%M:%S")

#         console = Console()
#         with console.status("[bold green]Working on tasks...") as status:
#             while waktu_sekarang != set_alarm:
#                 console.log(
#                     f"[yellow]{nama_matkul}[white] Target: [green]{tgt_jam}[white] Sekarang: [green]{waktu_sekarang}",
#                     justify="full",
#                 )
#                 waktu_sekarang = time.strftime("%H:%M:%S")
#                 time.sleep(1)

#                 if waktu_sekarang == set_alarm:
#                     self.ambil_link_absensi(url_matkul, nama_matkul, password_matkul)


class TimerEksekusi(Elearning):
    def __init__(self, nim: str, password: str, nomer_hp: str):
        super().__init__(nim, password, nomer_hp)
        self._runing = True

    def teriminate(self):
        self._runing = False

    def start(
        self,
        nama_matkul: str,
        url_matkul: str,
        password_matkul: str,
        tgt_jam: Union[str, datetime.datetime] = None,
    ):

        t = threading.Thread(
            target=self.run,
            args=(nama_matkul, url_matkul, password_matkul, tgt_jam),
        )
        t.daemon = True
        t.start()

    def run(
        self,
        nama_matkul: str,
        url_matkul: str,
        password_matkul: str,
        tgt_jam: Union[str, datetime.datetime] = None,
    ):

        set_alarm = str(tgt_jam)
        waktu_sekarang = time.strftime("%H:%M:%S")

        console = Console()
        with console.status("[bold green]Working on tasks...") as status:
            while self._runing:
                while waktu_sekarang != set_alarm:
                    console.log(
                        f"[yellow]{nama_matkul}[white] Target: [green]{tgt_jam}[white] Sekarang: [green]{waktu_sekarang}",
                        justify="full",
                    )
                    waktu_sekarang = time.strftime("%H:%M:%S")
                    time.sleep(1)

                    if waktu_sekarang == set_alarm:
                        super().ambil_link_absensi(url_matkul, nama_matkul, password_matkul)


class Main(Elearning):
    def __init__(
        self,
        nim: str,
        password: str,
        nomer_hp: str,
        path_jadwal: Union[Path, str] = None,
    ):
        super().__init__(nim, password, nomer_hp)
        self.nim = nim
        self.password = password
        self.nomer_hp = nomer_hp
        self.session = self.login()
        self.baca_jadwal = BacaJadwal(path_jadwal)
        self.eksekusi = TimerEksekusi(nim, passwd, nomer_hp)
        # self.alarm = Alarm(nim, password, nomer_hp)

    @property
    def ambil_nama_hari(self) -> datetime:
        return super().ambil_nama_hari

    def notifikasi(self, pesan: str, nomer_hp: str) -> None:
        return super().notifikasi(pesan, nomer_hp)

    def login(self) -> requests.sessions:
        return super().login()

    def run(self):
        hari_ini = self.ambil_nama_hari

        if hari_ini == "Monday":
            start_kolom = "A"
            end_kolom = "C"

            nested_list_matkul, list_nama_matkul = self.baca_jadwal.ambil_data_cell(start_kolom=start_kolom, end_kolom=end_kolom)
            if len(nested_list_matkul) != 0:
                self.setup_pesan_selamat_datang_perhari(hari_ini, nested_list_matkul, list_nama_matkul)
                self.setup_run(list_nama_matkul, nested_list_matkul)
            else:
                print("Tidak ada matkul untuk hari ini!")
                time.sleep(1)
                return

        elif hari_ini == "Tuesday":
            start_kolom = "D"
            end_kolom = "F"

            nested_list_matkul, list_nama_matkul = self.baca_jadwal.ambil_data_cell(start_kolom=start_kolom, end_kolom=end_kolom)
            if len(nested_list_matkul) != 0:
                self.setup_pesan_selamat_datang_perhari(hari_ini, nested_list_matkul, list_nama_matkul)
                self.setup_run(list_nama_matkul, nested_list_matkul)
            else:
                print("Tidak ada matkul untuk hari ini!")
                time.sleep(1)
                return

        elif hari_ini == "Wednesday":
            start_kolom = "G"
            end_kolom = "I"

            nested_list_matkul, list_nama_matkul = self.baca_jadwal.ambil_data_cell(start_kolom=start_kolom, end_kolom=end_kolom)
            if len(nested_list_matkul) != 0:
                self.setup_pesan_selamat_datang_perhari(hari_ini, nested_list_matkul, list_nama_matkul)
                self.setup_run(list_nama_matkul, nested_list_matkul)
            else:
                print("Tidak ada matkul untuk hari ini!")
                time.sleep(1)
                return

        elif hari_ini == "Thursday":
            start_kolom = "J"
            end_kolom = "L"

            nested_list_matkul, list_nama_matkul = self.baca_jadwal.ambil_data_cell(start_kolom=start_kolom, end_kolom=end_kolom)
            if len(nested_list_matkul) != 0:
                self.setup_pesan_selamat_datang_perhari(hari_ini, nested_list_matkul, list_nama_matkul)
                self.setup_run(list_nama_matkul, nested_list_matkul)
            else:
                print("Tidak ada matkul untuk hari ini!")
                time.sleep(1)
                return

        elif hari_ini == "Friday":
            start_kolom = "M"
            end_kolom = "O"

            nested_list_matkul, list_nama_matkul = self.baca_jadwal.ambil_data_cell(start_kolom=start_kolom, end_kolom=end_kolom)
            if len(nested_list_matkul) != 0:
                self.setup_pesan_selamat_datang_perhari(hari_ini, nested_list_matkul, list_nama_matkul)
                self.setup_run(list_nama_matkul, nested_list_matkul)
            else:
                print("Tidak ada matkul untuk hari ini!")
                time.sleep(1)
                return
        # libur
        else:
            start_kolom = ""
            end_kolom = ""

    def setup_pesan_selamat_datang_perhari(self, hari_ini: str, list_data_matkul: List[list], list_nama_matkul: list):
        teks_jam_matkul = ""
        list_jam_matkul = [item[0] for item in list_data_matkul]
        for jam, matkul in zip(list_jam_matkul, list_nama_matkul):
            teks_jam_matkul += f"*{jam} {matkul}*\n"

        pesan = f"Selamat hari *{hari_ini}*, kamu memiliki mata kuliah aktif:\n\n{teks_jam_matkul}"
        self.notifikasi(pesan, nomer_hp=self.nomer_hp)
        # print(pesan)

    def ambil_link_absensi(self, url_matkul: str, password: str = None) -> list:
        return super().ambil_link_absensi(url_matkul, password=password)

    def setup_run(self, list_nama_matkul: list, list_matkuls: List[list]):
        for idx, list_matkul in enumerate(list_matkuls):
            nama_matkul = list_nama_matkul[idx]
            jam, url, password = list_matkul
            # print(jam, url, password)
            self.eksekusi.start(nama_matkul, url, password, jam)


if __name__ == "__main__":
    lokasi_sekarang = Path.cwd()
    path_config = lokasi_sekarang / "config.ini"
    config = configparser.ConfigParser()
    config.read(filenames=path_config)

    nim = config["elearning"]["Nim"]
    passwd = config["elearning"]["Password"]
    nomer_hp = config["nomerhp"]["NomerHP"]
    jadwal = config["jadwal"]["JadwalFile"]
    bot = Main(nim, passwd, nomer_hp, jadwal)
    # TODO: menjalankan program 24/7 jam
    while True:
        bot.run()
        time.sleep(1)
