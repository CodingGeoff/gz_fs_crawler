"""所有站点适配器统一注册入口。"""
from .douban_gz import DoubanGZ
from .bendibao import BendibaoGZ, BendibaoFS
from .gzlib import GuangzhouLib
from .iwhyun import IwhYun
from .sdlib import ShundeLib
from .huodongxing import HuoDongXing
from .hudongba import HuDongBa
from .gz_arts import GZArts
from .foshan_culture_cloud import FoshanCultureCloud
from .foshan_lib import FoshanLib
from .nanhai_lib import NanhaiLib
from .foshanplus import FoshanPlus
from .damai import Damai
from .guangzhou_museum import GuangzhouMuseum
# 高校招聘/双选会
from .university_jobs import SYSUCareer, GDUTCareer, GZHUCareer
from .bibibi_career import SEIGCareer, JNUCareer
from .yingjiesheng import YingjieshengGZ
# 演出（占位）
from .showstart import ShowStart
from .ilivehouse import ILiveHouse
# 文化场馆 - 美术馆
from .gdmoa import GDMoA
from .times_museum import TimesMuseum
from .hxn_art import HXNArt
# 技术 / 大学生分享
from .segmentfault import SegmentFaultGZ
from .gdg_community import GDGCommunity
from .meetup_com import MeetupCom
from .eventbrite_gz import EventbriteGZ
from .sofastack import SOFAStack
# 哲学 / 学术
from .sysu_philosophy import SYSUPhilosophy

ALL_ADAPTERS = [
    # 活动 / 优惠 / 美食
    DoubanGZ,
    BendibaoGZ,
    BendibaoFS,
    HuoDongXing,
    HuDongBa,
    # 图书馆 / 文化馆 / 美术馆 / 博物馆
    GuangzhouLib,
    IwhYun,
    ShundeLib,
    NanhaiLib,
    GuangzhouMuseum,
    GDMoA,
    TimesMuseum,
    HXNArt,
    GZArts,
    FoshanCultureCloud,
    FoshanLib,
    FoshanPlus,
    # 演出
    Damai,
    ShowStart,
    ILiveHouse,
    # 校园招聘 / 宣讲会 / 双选会
    SYSUCareer,
    GDUTCareer,
    GZHUCareer,
    SEIGCareer,
    JNUCareer,
    YingjieshengGZ,
    # 技术 / 大学生分享
    SegmentFaultGZ,
    GDGCommunity,
    MeetupCom,
    EventbriteGZ,
    SOFAStack,
    # 哲学 / 学术
    SYSUPhilosophy,
]
