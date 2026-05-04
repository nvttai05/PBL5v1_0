import os
from sqlalchemy.orm import Session
from app.models.object_dictionary import ObjectDictionary
from app.models.user import User
from app.services.tts_service import tts_service


def seed_default_user(db: Session):
    """Tạo user mặc định user_id=1 nếu chưa có."""
    existing = db.query(User).filter(User.user_id == 1).first()
    if not existing:
        user = User(user_id=1, username="test_user", password="test123", role="student")
        db.add(user)
        db.commit()
        print("✅ Default test user created (user_id=1)")
    else:
        print(f"✅ User already exists: {existing.username}")




def seed_object_dictionary(db: Session):
    """Seed đủ 80 class COCO với nghĩa VN + câu ví dụ + IPA"""

    objects = [
        ("person", "người", "There is a person walking on the street.", "/ˈpɜːrsən/"),
        ("bicycle", "xe đạp", "I ride my bicycle to school every day.", "/ˈbaɪsɪkəl/"),
        ("car", "xe hơi", "My father drives a red car to work.", "/kɑːr/"),
        ("motorcycle", "xe máy", "He rides a fast motorcycle on the highway.", "/ˈmoʊtərˌsaɪkəl/"),
        ("airplane", "máy bay", "The airplane is flying high in the sky.", "/ˈerˌpleɪn/"),
        ("bus", "xe buýt", "The school bus arrives at 7 AM.", "/bʌs/"),
        ("train", "tàu hỏa", "We traveled by train last weekend.", "/treɪn/"),
        ("truck", "xe tải", "A big truck is delivering goods.", "/trʌk/"),
        ("boat", "thuyền", "We went fishing on a small boat.", "/boʊt/"),
        ("traffic light", "đèn giao thông", "The traffic light turned red.", "/ˈtræfɪk laɪt/"),
        ("fire hydrant", "vòi chữa cháy", "The fire hydrant is next to the sidewalk.", "/ˈfaɪər ˈhaɪdrənt/"),
        ("stop sign", "biển báo dừng", "The driver stopped at the stop sign.", "/stɑːp saɪn/"),
        ("parking meter", "đồng hồ đỗ xe", "He paid at the parking meter.", "/ˈpɑːrkɪŋ ˈmiːtər/"),
        ("bench", "ghế dài", "She sat on the bench in the park.", "/bentʃ/"),
        ("bird", "chim", "A beautiful bird is singing outside.", "/bɜːrd/"),
        ("cat", "mèo", "The cat is sleeping on the sofa.", "/kæt/"),
        ("dog", "chó", "The dog is barking loudly.", "/dɔːɡ/"),
        ("horse", "ngựa", "The horse is running across the field.", "/hɔːrs/"),
        ("sheep", "cừu", "The sheep are eating grass on the hill.", "/ʃiːp/"),
        ("cow", "bò", "The cow is standing in the farm.", "/kaʊ/"),
        ("elephant", "voi", "The elephant is very large and strong.", "/ˈelɪfənt/"),
        ("bear", "gấu", "The bear is walking through the forest.", "/ber/"),
        ("zebra", "ngựa vằn", "The zebra has black and white stripes.", "/ˈziːbrə/"),
        ("giraffe", "hươu cao cổ", "The giraffe has a very long neck.", "/dʒəˈræf/"),
        ("backpack", "ba lô", "My backpack is full of books.", "/ˈbækˌpæk/"),
        ("umbrella", "ô", "She opened her umbrella because it was raining.", "/ʌmˈbrelə/"),
        ("handbag", "túi xách", "Her handbag is on the chair.", "/ˈhændˌbæɡ/"),
        ("tie", "cà vạt", "He is wearing a blue tie today.", "/taɪ/"),
        ("suitcase", "vali", "The suitcase is packed for the trip.", "/ˈsuːtˌkeɪs/"),
        ("frisbee", "đĩa ném", "The children are throwing a frisbee.", "/ˈfrɪzbiː/"),
        ("skis", "ván trượt tuyết", "His skis are ready for the snow.", "/skiːz/"),
        ("snowboard", "ván trượt tuyết", "She rides her snowboard down the mountain.", "/ˈsnoʊˌbɔːrd/"),
        ("sports ball", "bóng thể thao", "The sports ball rolled across the field.", "/spɔːrts bɔːl/"),
        ("kite", "diều", "The kite is flying in the windy sky.", "/kaɪt/"),
        ("baseball bat", "gậy bóng chày", "He hit the ball with a baseball bat.", "/ˈbeɪsbɔːl bæt/"),
        ("baseball glove", "găng tay bóng chày", "She caught the ball with her baseball glove.", "/ˈbeɪsbɔːl ɡlʌv/"),
        ("skateboard", "ván trượt", "The boy is riding a skateboard.", "/ˈskeɪtˌbɔːrd/"),
        ("surfboard", "ván lướt sóng", "The surfboard is on the beach.", "/ˈsɜːrfˌbɔːrd/"),
        ("tennis racket", "vợt tennis", "She is holding a tennis racket.", "/ˈtenɪs ˈrækɪt/"),
        ("bottle", "chai", "There is a water bottle on the desk.", "/ˈbɑːtəl/"),
        ("wine glass", "ly rượu", "The wine glass is on the table.", "/waɪn ɡlæs/"),
        ("cup", "cốc", "I drink water from a blue cup.", "/kʌp/"),
        ("fork", "nĩa", "The fork is next to the plate.", "/fɔːrk/"),
        ("knife", "dao", "Be careful with the sharp knife.", "/naɪf/"),
        ("spoon", "muỗng", "She uses a spoon to eat soup.", "/spuːn/"),
        ("bowl", "bát", "The bowl is full of rice.", "/boʊl/"),
        ("banana", "chuối", "The banana is yellow and sweet.", "/bəˈnænə/"),
        ("apple", "táo", "I eat an apple every morning.", "/ˈæpəl/"),
        ("sandwich", "bánh mì kẹp", "He made a sandwich for lunch.", "/ˈsænwɪtʃ/"),
        ("orange", "cam", "The orange tastes fresh and juicy.", "/ˈɔːrɪndʒ/"),
        ("broccoli", "bông cải xanh", "Broccoli is a healthy vegetable.", "/ˈbrɑːkəli/"),
        ("carrot", "cà rốt", "The rabbit is eating a carrot.", "/ˈkærət/"),
        ("hot dog", "xúc xích kẹp bánh", "He bought a hot dog at the park.", "/ˈhɑːt dɔːɡ/"),
        ("pizza", "pizza", "We ordered a large pizza for dinner.", "/ˈpiːtsə/"),
        ("donut", "bánh donut", "The donut is covered with sugar.", "/ˈdoʊnʌt/"),
        ("cake", "bánh kem", "The birthday cake looks delicious.", "/keɪk/"),
        ("chair", "ghế", "Please sit on the wooden chair.", "/tʃer/"),
        ("couch", "ghế sofa", "The family is sitting on the couch.", "/kaʊtʃ/"),
        ("potted plant", "cây trồng trong chậu", "The potted plant is near the window.", "/ˈpɑːtɪd plænt/"),
        ("bed", "giường", "The baby is sleeping in the bed.", "/bed/"),
        ("dining table", "bàn ăn", "The plates are on the dining table.", "/ˈdaɪnɪŋ ˈteɪbəl/"),
        ("toilet", "bồn cầu", "The toilet is in the bathroom.", "/ˈtɔɪlət/"),
        ("tv", "ti vi", "We watch news on the TV every evening.", "/ˌtiːˈviː/"),
        ("laptop", "laptop", "My laptop is very useful for studying.", "/ˈlæpˌtɑːp/"),
        ("mouse", "chuột máy tính", "Move the mouse to click the icon.", "/maʊs/"),
        ("remote", "điều khiển từ xa", "The remote is on the sofa.", "/rɪˈmoʊt/"),
        ("keyboard", "bàn phím", "She is typing on the keyboard.", "/ˈkiːˌbɔːrd/"),
        ("cell phone", "điện thoại", "She is talking on her cell phone.", "/ˈsel foʊn/"),
        ("microwave", "lò vi sóng", "The food is heating in the microwave.", "/ˈmaɪkrəˌweɪv/"),
        ("oven", "lò nướng", "The bread is baking in the oven.", "/ˈʌvən/"),
        ("toaster", "máy nướng bánh mì", "The toaster is making hot bread.", "/ˈtoʊstər/"),
        ("sink", "bồn rửa", "Please wash your hands in the sink.", "/sɪŋk/"),
        ("refrigerator", "tủ lạnh", "The milk is inside the refrigerator.", "/rɪˈfrɪdʒəˌreɪtər/"),
        ("book", "sách", "I am reading an interesting book.", "/bʊk/"),
        ("clock", "đồng hồ", "The clock shows eight o’clock.", "/klɑːk/"),
        ("vase", "bình hoa", "The vase is filled with flowers.", "/veɪs/"),
        ("scissors", "cái kéo", "Use the scissors to cut the paper.", "/ˈsɪzərz/"),
        ("teddy bear", "gấu bông", "The child is hugging a teddy bear.", "/ˈtedi ber/"),
        ("hair drier", "máy sấy tóc", "She uses a hair drier after washing her hair.", "/ˈher ˌdraɪər/"),
        ("toothbrush", "bàn chải đánh răng", "I use a toothbrush every morning.", "/ˈtuːθˌbrʌʃ/"),
    ]

    count = 0

    for en, vn, sentence, ipa in objects:
        obj = db.query(ObjectDictionary).filter_by(class_name_en=en).first()

        if not obj:
            obj = ObjectDictionary(
                class_name_en=en,
                class_name_vn=vn,
                example_sentence_en=sentence,
                pronunciation_ipa=ipa
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
        else:
            # cập nhật nếu đã có sẵn
            obj.class_name_vn = vn
            obj.example_sentence_en = sentence
            obj.pronunciation_ipa = ipa
            db.commit()

        # tên file an toàn hơn
        safe_name = en.replace(" ", "_")
        audio_filename = f"{safe_name}.wav"
        audio_path = os.path.join("app/static/audio", audio_filename)

        if not os.path.exists(audio_path):
            try:
                result = tts_service.generate_audio(text=en)
                obj.audio_file_path = f"/static/audio/{audio_filename}"
                db.commit()
                count += 1
            except Exception as e:
                print(f"Failed for {en}: {e}")
        else:
            obj.audio_file_path = f"/static/audio/{audio_filename}"
            db.commit()

    print(f"Seed completed! Updated {count} objects with better examples and pronunciation.")