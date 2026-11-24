"""Normalisation for matching. The steps are the pack's, and OI-09 stays open."""

from __future__ import annotations

import unicodedata

from eii_core.text import normalise


def test_english_case_folding_matches_after_normalisation() -> None:
    assert normalise("Lusail") == normalise("lusail")
    assert normalise("Italian Restaurant") == normalise("italian restaurant")


def test_nfkc_and_case_fold_run_before_arabic_steps() -> None:
    assert normalise("\uff2c") == normalise("l")


def test_alef_variants_unify() -> None:
    assert normalise("\u0623\u0627") == normalise("\u0627\u0627")
    assert normalise("\u0625\u0627") == normalise("\u0627\u0627")
    assert normalise("\u0622\u0627") == normalise("\u0627\u0627")
    assert normalise("\u0671\u0627") == normalise("\u0627\u0627")


def test_diacritics_and_tatweel_are_removed() -> None:
    assert normalise("مَدْ") == normalise("مد")
    assert normalise("مـد") == normalise("مد")


def test_final_yaa_and_taa_marbuta_unify() -> None:
    assert normalise("فى") == normalise("في")
    assert normalise("بـة") == normalise("به")


def test_exact_nfc_is_not_the_normalised_form() -> None:
    folded = normalise("Lusail")
    exact = unicodedata.normalize("NFC", "Lusail")
    assert exact == "Lusail"
    assert folded != exact
