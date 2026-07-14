import pytest

from tg_vacancy_bot.resume_storage import ResumeStorage


def test_resume_storage_saves_and_deletes_pdf(tmp_path) -> None:
    storage = ResumeStorage(str(tmp_path / "private-resumes"), max_size_bytes=100)

    resume = storage.save(42, "resume.pdf", b"%PDF-1.7")

    assert resume.original_name == "resume.pdf"
    assert resume.stored_name.startswith("42-")
    assert storage.path_for(resume.stored_name).read_bytes() == b"%PDF-1.7"
    assert storage.delete(resume.stored_name) is True
    assert storage.delete(resume.stored_name) is False


def test_resume_storage_accepts_docx(tmp_path) -> None:
    storage = ResumeStorage(str(tmp_path / "private-resumes"), max_size_bytes=100)

    resume = storage.save(42, "resume.docx", b"PK\x03\x04")

    assert storage.path_for(resume.stored_name).suffix == ".docx"


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("resume.txt", b"text", "PDF or DOCX"),
        ("../resume.pdf", b"content", "must not contain a path"),
        ("resume.pdf", b"", "empty"),
        ("resume.pdf", b"too long", "size limit"),
    ],
)
def test_resume_storage_rejects_invalid_uploads(tmp_path, name, content, message) -> None:
    storage = ResumeStorage(str(tmp_path / "private-resumes"), max_size_bytes=3)

    with pytest.raises(ValueError, match=message):
        storage.save(42, name, content)
