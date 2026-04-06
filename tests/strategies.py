from hypothesis import strategies as st

# Strategy for generating message record data
message_records = st.fixed_dictionaries({
    "sender": st.text(min_size=1, max_size=50),
    "content": st.text(min_size=1, max_size=500),
    "timestamp": st.integers(min_value=0, max_value=2000000000000),
    "status": st.sampled_from(["READ", "DELIVERED", "DELETED"]),
    "is_deleted": st.booleans(),
    "read_timestamp": st.one_of(st.none(), st.integers(min_value=0, max_value=2000000000000)),
    "delivered_timestamp": st.one_of(st.none(), st.integers(min_value=0, max_value=2000000000000)),
})

notification_records = st.fixed_dictionaries({
    "sender": st.text(min_size=1, max_size=50),
    "content": st.text(min_size=1, max_size=500),
    "timestamp": st.integers(min_value=0, max_value=2000000000000),
    "app_package": st.sampled_from(["com.whatsapp", "com.instagram", "com.twitter", "com.facebook"]),
})

artifact_bytes = st.binary(min_size=1, max_size=10000)

case_inputs = st.fixed_dictionaries({
    "case_number": st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-"),
    ),
    "investigator_id": st.text(min_size=1, max_size=50),
})

media_file_names = st.sampled_from([
    "photo.jpg", "image.png", "pic.gif", "snap.webp", "shot.jpeg",
    "clip.mp4", "video.3gp", "movie.mkv", "rec.avi",
    "voice.opus", "song.mp3", "audio.aac", "sound.ogg",
    "report.pdf", "file.doc", "sheet.xlsx", "doc.docx", "data.xls",
])
