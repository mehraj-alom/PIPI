<div align="center">

# 🩺 SKIN_TELLIGENT

### AI Decision Support System for Dermatology Assistance

<br/>

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge)](LICENSE)

<br/>

![Status](https://img.shields.io/badge/Version-2.0_Active-22C55E?style=flat-square)
![Classes](https://img.shields.io/badge/Skin_Conditions-27_Classes-8B5CF6?style=flat-square)
![Accuracy](https://img.shields.io/badge/Macro_F1-84.1%25-F97316?style=flat-square)
![Architecture](https://img.shields.io/badge/Model-EfficientNet--B4-06B6D4?style=flat-square)

<br/>

> **⚠️ Medical Disclaimer** — This project is built strictly for **research and educational purposes only**.
> It should never be used for real medical diagnosis.
> Please consult a qualified healthcare professional for any medical concerns.

<br/>

<img src="https://i.ibb.co/hJfvCpD3/pipeline-overview.png" alt="Pipeline Overview" width="780"/>

</div>

<br/>

---

## 📌 Overview

**SKIN_TELLIGENT** is a multi-stage AI decision-support system that performs image-based skin region analysis, provides model explainability via **Grad-CAM++**, and conditionally controls output based on prediction confidence — designed to avoid presenting unreliable results in safety-sensitive contexts.

The system is **not a diagnostic tool**. It is an educational demonstration of:

- 🔍 **Multi-stage inference** with structured handoffs between detection and classification
- 🔐 **Confidence-gated output** — uncertain predictions are never shown as facts
- 🧠 **Explainability integration** — every prediction traces back to specific image regions
- 🏥 **27-class classification** trained on a publicly available dermatology dataset

<div align="right">

**Author**: [Mehraj Alom Tapadar](https://www.linkedin.com/in/mehraj-alom-tapadar-b1abb025b) &nbsp;·&nbsp; [GitHub](https://github.com/mehraj-alom/SKIN_DISEASE_CLASSIFIER)

</div>

---

## 🔍 The Problem

Skin diseases affect hundreds of millions of people globally, and early identification is directly tied to treatment outcomes.

<table>
<tr>
<td width="50%">

**⏱️ Capacity constraints**
Dermatologists carry high patient volumes, leaving limited time per case

</td>
<td width="50%">

**🌍 Access gaps**
Specialist access is severely limited in rural and remote areas

</td>
</tr>
<tr>
<td>

**🎓 Experience dependency**
Initial screening relies heavily on years of clinical exposure

</td>
<td>

**🔬 Visual complexity**
27 overlapping conditions are difficult to distinguish without training

</td>
</tr>
</table>

This project explores whether AI can meaningfully assist with preliminary screening — not to replace clinical judgment, but to support it.

---

## 🏗️ System Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Image Input    │────▶│  YOLO Detection  │────▶│  ROI Extraction │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Grad-CAM++     │◀────│  Classification  │◀────│  Confidence     │
│  Explainability │     │  (27 classes)    │     │  Gating         │
└────────┬────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Conditional Interface Layer                                      │
│  HIGH  (≥ 80%)   →  Full results + Grad-CAM++ explainability     │
│  UNCERTAIN       →  Limited context + explicit uncertainty notice │
│  ABSTAIN (< 60%) →  Professional referral only — no output shown │
└──────────────────────────────────────────────────────────────────┘
```

### 🔐 Decision Governance

A low-confidence prediction that looks authoritative is more harmful than showing nothing at all. The system abstains gracefully when it isn't sure.

<div align="center">

| Confidence | State | What the user sees |
|:---:|:---:|:---|
| ≥ 80% | 🟢 `HIGH_CONFIDENCE` | Full classification + Grad-CAM++ heatmap |
| 60–80% | 🟡 `UNCERTAIN` | Condition name with explicit uncertainty message |
| < 60% | 🔴 `ABSTAIN` | Professional referral only — no classification shown |

</div>

All inference decisions are logged with confidence scores for auditability.

---

## 📊 Model Performance

The classifier went through two major versions. The jump from v1.0 → v2.0 came primarily from **fixing silent bugs in the training pipeline**, not just from switching architectures.

> 📓 **For a deeper dive** into the old vs new model comparison — training logs, metrics breakdown, and analysis — see the **[Kaggle Notebook](https://www.kaggle.com/code/mehrajalomtapadar/notebooka1e763f51a)**.

### Overall Metrics

<div align="center">

|  | v1.0 — Old_model | v2.0 — New_model | Δ |
|:---|:---:|:---:|:---:|
| **Accuracy** | 71.1% | **82.3%** | `+11.2%` |
| **Macro Precision** | 67.1% | **80.3%** | `+13.2%` |
| **Macro Recall** | 77.0% | **91.4%** | `+14.4%` |
| **Macro F1** | 70.1% | **84.1%** | `+14.0%` |
| **Weighted F1** | 72.1% | **82.7%** | `+10.6%` |

</div>

> 💡 **Notable signal**: In v2.0, Macro F1 **(84.1%)** is higher than Weighted F1 **(82.7%)**. This means the model performs better on minority classes than on majority ones — exactly what the class-balancing strategy was designed to achieve. In v1.0, the pattern was reversed, indicating strong majority-class bias.

<br/>

### Per-Class F1 — v1.0 vs v2.0

<div align="center">

| Skin Condition | v1.0 | v2.0 | Δ |
|:---|:---:|:---:|:---:|
| Cutaneous Larva Migrans | 1.00 | **1.00** | — |
| Dermatofibroma | 0.90 | **1.00** | `+0.10` ✨ |
| Shingles | 0.82 | **0.98** | `+0.16` |
| Oily Skin | 0.87 | **0.97** | `+0.10` |
| Vitiligo | 0.83 | **0.97** | `+0.14` |
| Chickenpox | 0.91 | **0.94** | `+0.03` |
| Acne | 0.88 | **0.94** | `+0.06` |
| Dry Skin | 0.75 | **0.94** | `+0.19` |
| Warts | 0.84 | **0.93** | `+0.09` |
| Rosacea | 0.88 | **0.91** | `+0.03` |
| Actinic Keratosis | 0.81 | **0.91** | `+0.10` |
| Rashes | 0.77 | **0.90** | `+0.13` |
| Herpes | 0.64 | **0.89** | `+0.25` 🔼 |
| Hidradenitis Suppurativa | 0.65 | **0.89** | `+0.24` 🔼 |
| Nail Fungus & Nail Disease | 0.84 | **0.88** | `+0.04` |
| Poison Ivy & Contact Dermatitis | 0.67 | **0.86** | `+0.19` |
| Bullous Disease | 0.62 | **0.83** | `+0.21` |
| Urticaria (Hives) | 0.66 | **0.82** | `+0.16` |
| Light Diseases & Pigmentation | 0.51 | **0.82** | `+0.31` 🔼 |
| Exanthems & Drug Eruptions | 0.62 | **0.78** | `+0.16` |
| Dermatitis | 0.52 | **0.75** | `+0.23` |
| Other Diseases | 0.36 | **0.74** | `+0.38` 🔼 |
| Lupus & Connective Tissue Diseases | 0.57 | **0.70** | `+0.13` |
| Eczema | 0.57 | **0.67** | `+0.10` |
| Psoriasis & Lichen Planus | 0.58 | **0.66** | `+0.08` |
| Atopic Dermatitis | 0.46 | **0.63** | `+0.17` |
| Hair Loss / Alopecia | 0.40 | **0.42** | `+0.02` |

</div>

> ✅ **v2.0 improved on every single class — zero regressions.** The largest gains were in low-support minority classes (Other Diseases +0.38, Light Diseases +0.31, Herpes +0.25) — exactly the conditions being suppressed by class imbalance in v1.0.

<br/>

### What Changed Between Versions

<div align="center">

| Area | v1.0 ❌ | v2.0 ✅ |
|:---|:---|:---|
| Pretrained weights | B4 loaded without ImageNet weights (silent bug) | All variants load `IMAGENET1K_V1` correctly |
| LR scheduler | Passed as class object — never activated | Passed as string — activates correctly |
| Class weight scale | Normalised to sum=1, killing loss signal | Raw effective-number-of-samples (CVPR 2019) |
| Classifier head | Plain `Linear` layer | `Dropout(0.4)` + `Linear` |
| Backbone training | Full fine-tune — 17.6M trainable params | Partial freeze — last 2 blocks + head (~3M) |
| Augmentation | Flip + rotation only | + Affine, grayscale, stronger colour jitter |
| Batch size | 16 | 32 |
| Early stopping | None | Patience = 5 on Macro F1 |

</div>

---

## 🏥 Supported Skin Conditions

<div align="center">

| # | Condition | # | Condition | # | Condition |
|:---:|:---|:---:|:---|:---:|:---|
| 1 | Acne | 10 | Exanthems & Drug Eruptions | 19 | Cutaneous Larva Migrans |
| 2 | Actinic Keratosis | 11 | Hair Loss (Alopecia) | 20 | Poison Ivy & Contact Dermatitis |
| 3 | Atopic Dermatitis | 12 | Herpes | 21 | Psoriasis & Lichen Planus |
| 4 | Bullous Disease | 13 | Hidradenitis Suppurativa | 22 | Rashes |
| 5 | Chickenpox | 14 | Light Diseases & Pigmentation | 23 | Rosacea |
| 6 | Dermatitis | 15 | Lupus & Connective Tissue | 24 | Shingles |
| 7 | Dermatofibroma | 16 | Nail Fungus & Nail Disease | 25 | Urticaria (Hives) |
| 8 | Dry Skin | 17 | Oily Skin | 26 | Vitiligo |
| 9 | Eczema | 18 | Other Diseases | 27 | Warts |

</div>

---

## 🛠️ Tech Stack

<div align="center">

| Layer | Technology | Purpose |
|:---:|:---:|:---|
| 🎯 Detection | **YOLO v8** | Skin region localisation and ROI extraction |
| 🧠 Classification | **PyTorch — EfficientNet-B4** | 27-class condition identification |
| 🔍 Explainability | **Grad-CAM++** | Visual attribution of model decisions |
| ⚙️ HPO | **Optuna** | Automated architecture and learning rate search |
| 🔌 API | **FastAPI + Pydantic** | REST backend with schema validation |
| 🚀 Training | **Kaggle (free GPU)** | Model training and evaluation |
| 🔬 Tuning | **Google Colab** | Hyperparameter search compute |

</div>