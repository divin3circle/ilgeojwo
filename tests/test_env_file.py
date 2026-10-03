from ilgeojwo.env import load_env_file


def test_a_local_env_file_supplies_settings(tmp_path):
    f = tmp_path / ".ilgeojwo.env"
    f.write_text("# her machine\nILGEOJWO_LLM_MODEL=exaone3.5:7.8b\n\n"
                 "ILGEOJWO_OCR_GPU=1\n", encoding="utf-8")
    env = {}
    load_env_file(f, env)
    assert env == {"ILGEOJWO_LLM_MODEL": "exaone3.5:7.8b", "ILGEOJWO_OCR_GPU": "1"}


def test_the_real_environment_always_wins_over_the_file(tmp_path):
    """Otherwise a stale file would silently override a deliberate override."""
    f = tmp_path / ".ilgeojwo.env"
    f.write_text("ILGEOJWO_LLM_MODEL=exaone3.5:7.8b\n", encoding="utf-8")
    env = {"ILGEOJWO_LLM_MODEL": "exaone3.5:2.4b"}
    load_env_file(f, env)
    assert env["ILGEOJWO_LLM_MODEL"] == "exaone3.5:2.4b"


def test_a_missing_file_is_not_an_error(tmp_path):
    env = {}
    load_env_file(tmp_path / "nope.env", env)
    assert env == {}


def test_junk_lines_are_skipped_rather_than_crashing_the_launcher(tmp_path):
    f = tmp_path / ".ilgeojwo.env"
    f.write_text("not a pair\n=novalue\nILGEOJWO_PORT=9000\n", encoding="utf-8")
    env = {}
    load_env_file(f, env)
    assert env == {"ILGEOJWO_PORT": "9000"}


def test_quotes_and_whitespace_are_stripped(tmp_path):
    f = tmp_path / ".ilgeojwo.env"
    f.write_text('  ILGEOJWO_LLM_MODEL = "exaone3.5:7.8b"  \n', encoding="utf-8")
    env = {}
    load_env_file(f, env)
    assert env["ILGEOJWO_LLM_MODEL"] == "exaone3.5:7.8b"
