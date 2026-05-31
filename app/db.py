from sqlmodel import SQLModel, create_engine, Session, select
from .config import settings
from .models import Holding

engine = create_engine(settings.database_url, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)
    seed_default_holding()

def get_session():
    with Session(engine) as session:
        yield session

def seed_default_holding():
    with Session(engine) as session:
        existing = session.exec(select(Holding).where(Holding.ticker == "285A")).first()
        if existing:
            return
        holding = Holding(
            ticker="285A",
            name="キオクシアホールディングス",
            market="JP",
            thesis=(
                "AIデータセンター拡大によりNANDフラッシュと大容量ストレージ需要が増え、"
                "NAND市況改善・利益率改善・海外投資家の認知拡大を通じて中長期的な株価上昇が期待できる。"
            ),
            positive_keywords="NAND価格上昇,AIデータセンター,SSD需要,HBM周辺需要,業績上方修正,海外投資家,ADS,増配,自社株買い",
            negative_keywords="NAND価格下落,供給過剰,競合増産,Samsung増産,Micron増産,SK hynix増産,減益,下方修正,大株主売却,設備投資負担",
            competitors="Samsung,Micron,SK hynix,Western Digital,Sandisk"
        )
        session.add(holding)
        session.commit()
