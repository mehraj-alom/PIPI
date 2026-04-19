from datetime import time
from typing import Any

from backend.database.connections import SessionLocal
from backend.database.models import Doctor


DOCTORS = [
  {"name":"Dr. Aisha Rahman","specialization":"Dermatology","phone":"+919800000001","email":"aisha.rahman@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Neha Kapoor","specialization":"Dermatology","phone":"+919800000002","email":"neha.kapoor@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Arjun Singh","specialization":"Dermatology","phone":"+919800000003","email":"arjun.singh@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Pooja Nair","specialization":"Dermatology","phone":"+919800000004","email":"pooja.nair@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Sameer Khan","specialization":"Dermatology","phone":"+919800000005","email":"sameer.khan@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Vikram Mehta","specialization":"Cardiology","phone":"+919800000006","email":"vikram.mehta@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"16:00:00","slot_duration":15},
  {"name":"Dr. Rahul Verma","specialization":"Cardiology","phone":"+919800000007","email":"rahul.verma@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},
  {"name":"Dr. Sneha Iyer","specialization":"Cardiology","phone":"+919800000008","email":"sneha.iyer@optimacare.com","available_days":["tuesday","friday","sunday"],"slot_start":"12:00:00","slot_end":"20:00:00","slot_duration":15},
  {"name":"Dr. Karan Shah","specialization":"Cardiology","phone":"+919800000009","email":"karan.shah@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Ankit Jain","specialization":"Cardiology","phone":"+919800000010","email":"ankit.jain@optimacare.com","available_days":["monday","thursday","sunday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},

  {"name":"Dr. Meera Das","specialization":"Neurology","phone":"+919800000011","email":"meera.das@optimacare.com","available_days":["monday","thursday","saturday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Abhishek Roy","specialization":"Neurology","phone":"+919800000012","email":"abhishek.roy@optimacare.com","available_days":["tuesday","friday","sunday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Kavita Sharma","specialization":"Neurology","phone":"+919800000013","email":"kavita.sharma@optimacare.com","available_days":["wednesday","saturday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Aman Gupta","specialization":"Neurology","phone":"+919800000014","email":"aman.gupta@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Ritu Agarwal","specialization":"Neurology","phone":"+919800000015","email":"ritu.agarwal@optimacare.com","available_days":["thursday","friday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Rohan Paul","specialization":"General Physician","phone":"+919800000016","email":"rohan.paul@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Anjali Sen","specialization":"General Physician","phone":"+919800000017","email":"anjali.sen@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Imran Ali","specialization":"General Physician","phone":"+919800000018","email":"imran.ali@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Priya Das","specialization":"General Physician","phone":"+919800000019","email":"priya.das@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Saurav Dutta","specialization":"General Physician","phone":"+919800000020","email":"saurav.dutta@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Pankaj Yadav","specialization":"Orthopedic","phone":"+919800000021","email":"pankaj.yadav@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Shreya Bose","specialization":"Orthopedic","phone":"+919800000022","email":"shreya.bose@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Rohit Sen","specialization":"Orthopedic","phone":"+919800000023","email":"rohit.sen@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Kavya Reddy","specialization":"Orthopedic","phone":"+919800000024","email":"kavya.reddy@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Amit Sharma","specialization":"Orthopedic","phone":"+919800000025","email":"amit.sharma@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},
  {"name":"Dr. Riya Gupta","specialization":"Pediatrics","phone":"+919800000026","email":"riya.gupta@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Nikhil Das","specialization":"Pediatrics","phone":"+919800000027","email":"nikhil.das@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Sonali Roy","specialization":"Pediatrics","phone":"+919800000028","email":"sonali.roy@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Ajay Kulkarni","specialization":"Pediatrics","phone":"+919800000029","email":"ajay.kulkarni@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Farhan Ali","specialization":"Pediatrics","phone":"+919800000030","email":"farhan.ali@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Deepika Menon","specialization":"ENT","phone":"+919800000031","email":"deepika.menon@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Varun Khanna","specialization":"ENT","phone":"+919800000032","email":"varun.khanna@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Kunal Bose","specialization":"ENT","phone":"+919800000033","email":"kunal.bose@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Radhika Iyer","specialization":"ENT","phone":"+919800000034","email":"radhika.iyer@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Zubair Khan","specialization":"ENT","phone":"+919800000035","email":"zubair.khan@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Ishita Sen","specialization":"Ophthalmology","phone":"+919800000036","email":"ishita.sen@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Rakesh Pillai","specialization":"Ophthalmology","phone":"+919800000037","email":"rakesh.pillai@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Tania Dutta","specialization":"Ophthalmology","phone":"+919800000038","email":"tania.dutta@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Manoj Patil","specialization":"Ophthalmology","phone":"+919800000039","email":"manoj.patil@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Sana Sheikh","specialization":"Ophthalmology","phone":"+919800000040","email":"sana.sheikh@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Ankit Roy","specialization":"Psychiatry","phone":"+919800000041","email":"ankit.roy@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Priyanka Sinha","specialization":"Psychiatry","phone":"+919800000042","email":"priyanka.sinha@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Rohan Mitra","specialization":"Psychiatry","phone":"+919800000043","email":"rohan.mitra@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Kavya Nair","specialization":"Psychiatry","phone":"+919800000044","email":"kavya.nair@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Danish Ali","specialization":"Psychiatry","phone":"+919800000045","email":"danish.ali@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Shalini Verma","specialization":"Gynecology","phone":"+919800000046","email":"shalini.verma@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Pooja Singh","specialization":"Gynecology","phone":"+919800000047","email":"pooja.singh@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Reema Das","specialization":"Gynecology","phone":"+919800000048","email":"reema.das@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Nisha Kapoor","specialization":"Gynecology","phone":"+919800000049","email":"nisha.kapoor@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Farida Begum","specialization":"Gynecology","phone":"+919800000050","email":"farida.begum@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},
  {"name":"Dr. Alok Banerjee","specialization":"Gastroenterology","phone":"+919800000051","email":"alok.banerjee@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Snehal Patil","specialization":"Gastroenterology","phone":"+919800000052","email":"snehal.patil@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Vivek Sharma","specialization":"Gastroenterology","phone":"+919800000053","email":"vivek.sharma@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Priyanka Das","specialization":"Gastroenterology","phone":"+919800000054","email":"priyanka.das@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Faiz Ahmed","specialization":"Gastroenterology","phone":"+919800000055","email":"faiz.ahmed@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Karthik Reddy","specialization":"Urology","phone":"+919800000056","email":"karthik.reddy@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Manish Tiwari","specialization":"Urology","phone":"+919800000057","email":"manish.tiwari@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Rohini Nair","specialization":"Urology","phone":"+919800000058","email":"rohini.nair@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Ajit Kulkarni","specialization":"Urology","phone":"+919800000059","email":"ajit.kulkarni@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Salman Qureshi","specialization":"Urology","phone":"+919800000060","email":"salman.qureshi@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Mehul Shah","specialization":"Pulmonology","phone":"+919800000061","email":"mehul.shah@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Ritu Chatterjee","specialization":"Pulmonology","phone":"+919800000062","email":"ritu.chatterjee@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Akash Gupta","specialization":"Pulmonology","phone":"+919800000063","email":"akash.gupta@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Neelam Singh","specialization":"Pulmonology","phone":"+919800000064","email":"neelam.singh@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Imtiyaz Khan","specialization":"Pulmonology","phone":"+919800000065","email":"imtiyaz.khan@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Shweta Mishra","specialization":"Endocrinology","phone":"+919800000066","email":"shweta.mishra@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Gaurav Jain","specialization":"Endocrinology","phone":"+919800000067","email":"gaurav.jain@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Rina Das","specialization":"Endocrinology","phone":"+919800000068","email":"rina.das@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Pankaj Verma","specialization":"Endocrinology","phone":"+919800000069","email":"pankaj.verma@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Tanveer Alam","specialization":"Endocrinology","phone":"+919800000070","email":"tanveer.alam@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15},

  {"name":"Dr. Kavita Mehta","specialization":"Oncology","phone":"+919800000071","email":"kavita.mehta@optimacare.com","available_days":["monday","wednesday","friday"],"slot_start":"09:00:00","slot_end":"17:00:00","slot_duration":15},
  {"name":"Dr. Rakesh Yadav","specialization":"Oncology","phone":"+919800000072","email":"rakesh.yadav@optimacare.com","available_days":["tuesday","thursday","saturday"],"slot_start":"10:00:00","slot_end":"18:00:00","slot_duration":15},
  {"name":"Dr. Nupur Sen","specialization":"Oncology","phone":"+919800000073","email":"nupur.sen@optimacare.com","available_days":["monday","tuesday","sunday"],"slot_start":"08:00:00","slot_end":"14:00:00","slot_duration":15},
  {"name":"Dr. Harsh Vardhan","specialization":"Oncology","phone":"+919800000074","email":"harsh.vardhan@optimacare.com","available_days":["wednesday","thursday","saturday"],"slot_start":"11:00:00","slot_end":"19:00:00","slot_duration":15},
  {"name":"Dr. Farooq Ali","specialization":"Oncology","phone":"+919800000075","email":"farooq.ali@optimacare.com","available_days":["friday","saturday","sunday"],"slot_start":"09:00:00","slot_end":"15:00:00","slot_duration":15}

]



def _parse_time(value: Any, default_value: time) -> time:
  if isinstance(value, time):
    return value
  if isinstance(value, str):
    try:
      return time.fromisoformat(value.strip())
    except ValueError:
      return default_value
  return default_value


def seed_doctors() -> None:
  session = SessionLocal()
  created = 0
  skipped = 0

  try:
    for raw in DOCTORS:
      name = str(raw.get("name", "")).strip()
      specialization = str(raw.get("specialization", "")).strip()
      phone = raw.get("phone")
      email = raw.get("email")

      if not name or not specialization:
        skipped += 1
        continue

      existing = (
        session.query(Doctor)
        .filter(
          Doctor.name == name,
          Doctor.specialization == specialization,
          Doctor.phone == phone,
          Doctor.email == email,
        )
        .first()
      )
      if existing:
        skipped += 1
        continue

      doctor = Doctor(
        name=name,
        specialization=specialization,
        phone=phone,
        email=email,
        available_days=raw.get("available_days") or [],
        slot_start=_parse_time(raw.get("slot_start"), time(9, 0)),
        slot_end=_parse_time(raw.get("slot_end"), time(17, 0)),
        slot_duration=int(raw.get("slot_duration") or 30),
      )
      session.add(doctor)
      created += 1

    session.commit()
    print(f"Seed complete. Created: {created}, Skipped: {skipped}")
  except Exception:
    session.rollback()
    raise
  finally:
    session.close()


if __name__ == "__main__":
  seed_doctors()
