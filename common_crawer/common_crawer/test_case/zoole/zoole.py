import csv
import json
import os

import gevent
import pandas as pd
import random
import re
import time
from multiprocessing.pool import Pool
from urllib.parse import quote

import requests
from lxml import etree
import demjson


# TODO 协程
# TODO 过滤重复请求
# TODO 直接存为excel

def get_base(features_Ele, item):
    for i in features_Ele:
        if 'bedroom' in i:
            bedroom_num = ''.join(re.findall("\d+\.?\d*", i))
            item['bedroom_num'] = bedroom_num
        if 'bathroom' in i:
            bathroom_num = ''.join(re.findall("\d+\.?\d*", i))
            item['bathroom_num'] = bathroom_num
        if 'reception room' in i:
            reception_room_num = ''.join(re.findall("\d+\.?\d*", i))
            item['reception_room_num'] = reception_room_num
        if 'furnished' in i or 'Furnished' in i:
            item['furnish_codition'] = i


def get_distance(distance, item):
    subway_distance = []
    school_distance = []
    for i in distance[0:3]:
        if 'miles' in i:
            subway_distance.append(''.join(re.findall("\d+\.?\d*", i)))
    for i in distance[3:]:
        if 'miles' in i:
            school_distance.append(''.join(re.findall("\d+\.?\d*", i)))
    subway_distance = min(subway_distance)
    school_distance = min(school_distance)
    item['subway_distance'] = subway_distance
    item['school_distance'] = school_distance


def detect(descrition, item):
    for x in descrition:
        if 'garden' in x:
            item['has_garden'] = 1
        if 'modern' in x or 'high standard' in x or 'good qualitu' in x or 'renovated' in x:
            item['has_modern_etc'] = 1


def get_agent(detail_tree, item):
    agentName = ''.join(list(filter(lambda t: t != '', map(lambda x: x.strip(), detail_tree.xpath(
        "//h4[@class='ui-agent__name']//text()")))))
    agentAddress = ''.join(list(filter(lambda t: t != '', map(lambda x: x.strip(), detail_tree.xpath(
        "//address[@class='ui-agent__address']//text()"))))[0])
    try:
        agentPhone = ''.join(list(filter(lambda t: t != '', map(lambda x: x.strip(), detail_tree.xpath(
            "//p[@class='ui-agent__tel ui-agent__text']/a//text()")[1]))))
    except Exception as e:
        print(e)
    else:
        item['agentPhone'] = agentPhone
    item['agentName'] = agentName
    item['agentAddress'] = agentAddress


def get_mapData(res, item):
    mapData = res.text[
              res.text.find('ZPG.mapData') + len('ZPG.mapData = '):res.text.find(
                  'ZPG.poiMapData = ')].strip().strip(
        ';')
    mapData = json.loads(mapData)
    bounding_box = mapData['bounding_box']
    coordinates = mapData['coordinates']
    del coordinates['is_approximate']
    item.update(bounding_box)
    item.update(coordinates)
    # area_info = res.text[res.text.find('ZPG.mapData'):res.text.find('ZPG.poiMapData')]
    # bounding_box = area_info[area_info.find('"bounding_box"') + len('"bounding_box":'):area_info.find(
    #     '"coordinates"')].strip().strip(',')
    # print(bounding_box)
    # coordinates = area_info[
    #               area_info.find('"coordinates"') + len('"coordinates":'):area_info.find('"pin"')].strip().strip(',')
    # bounding_box = json.loads(bounding_box)
    # coordinates = json.loads(coordinates)
    address_info = res.text[
                   res.text.find('ZPG.trackData.taxonomy') + len('ZPG.trackData.taxonomy = '):res.text.find(
                       'ZPG.trackData.taxonomy.activity')].strip().strip(';')
    address_info = demjson.decode(address_info)
    item['area_name'] = address_info['area_name']
    item['country_code'] = address_info['country_code']
    item['county_area_name'] = address_info['county_area_name']
    item['room_category'] = address_info['listings_category']
    item['postal_area'] = address_info['postal_area']
    item['region_name'] = address_info['region_name']
    item['outcode'] = address_info['outcode']
    item['post_town_name'] = address_info['post_town_name']
    item['branch_name'] = address_info['branch_name']
    item['brand_name'] = address_info['brand_name']
    item['display_address'] = address_info['display_address']
    item['furnished_state'] = address_info['furnished_state']
    item['has_epc'] = address_info['has_epc']
    item['has_floorplan'] = address_info['has_floorplan']
    item['incode'] = address_info['incode']
    item['is_retirement_home'] = address_info['is_retirement_home']
    item['is_shared_ownership'] = address_info['is_shared_ownership']
    item['room_status'] = address_info['listing_status']
    item['num_baths'] = address_info['num_baths']
    item['num_beds'] = address_info['num_beds']
    item['num_recepts'] = address_info['num_recepts']
    item['property_type'] = address_info['property_type']
    item['zindex'] = address_info['zindex']
    item['room_condition'] = address_info['listing_condition']


def parse(res, bigAddress, id):
    try:
        item = {}
        item['has_garden'] = 0
        item['has_modern_etc'] = 0
        item['has_flat_studio'] = 0
        item['has_house'] = 0
        detail_tree = etree.HTML(res.text)
        market_stats = ''.join(detail_tree.xpath("//span[@class='dp-market-stats__price']//text()"))
        descrition = list(filter(lambda t: t != '', map(lambda x: x.strip(), detail_tree.xpath(
            "//section[@class='dp-features']/ul[@class='dp-features__list ui-list-bullets']//text()"))))
        # if market_stats=='':
        #     print('重新请求',market_stats,descrition_info)
        #     parse(requests.get(detail_url), detail_url)
        # else:
        price = ''.join(list(filter(lambda t: t != '', map(lambda x: x.strip(), detail_tree.xpath(
            "//div[@class='dp-sidebar-wrapper']//div[@class='ui-pricing']/p[@class='ui-pricing__main-price']//text()")))))
        price = ''.join(re.findall("\d+\.?\d*", price))
        # property_info_Ele = detail_tree.xpath(
        #     "//ul[@class='dp-features__list ui-list-icons']//text()")
        # features_Ele = filter(lambda t: t != '', map(lambda x: x.strip(), property_info_Ele))
        # get_base(features_Ele,item)
        detect(descrition, item)
        descrition = ','.join(descrition)
        price_history_date = ''.join(detail_tree.xpath("//span[@class='dp-price-history__item-date']//text()"))
        distance = detail_tree.xpath(
            "//div[@class='ui-interactive-map']//ul[@class='ui-local-amenities__list ui-list-flat']//text()")
        distance = list(filter(lambda t: t != '', map(lambda x: x.strip(), distance)))
        get_distance(distance, item)
        market_stats = ''.join(re.findall("\d+\.?\d*", market_stats))

        # address = ','.join(list(filter(lambda t: t != '', map(lambda x: x.strip(), detail_tree.xpath(
        #     "//h2[@class='ui-prop-summary__address']/text()")))))

        title = ''.join(list(filter(lambda t: t != '', map(lambda x: x.strip(), detail_tree.xpath(
            "//h1[@class='ui-prop-summary__title ui-title-subgroup']/text()")))))
        get_agent(detail_tree, item)
        if 'flat' in title or 'studio' in title:
            item['has_flat_studio'] = 1
        if 'house' in title:
            item['has_house'] = 1
        # area_name=res.text[res.text.find('area_name')+len('area_name:'):res.text.find('beds_max')]
        # streetAddress=res.text[res.text.find('streetAddress')+len('streetAddress'):res.text.find('postalCode')-1]
        # postcode=res.text[res.text.find('postalCode')+len('postalCode'):res.text.find(')')]
        # town=res.text[res.text.find('post_town_name')+len('post_town_name'):res.text.find('postal_area')]
        get_mapData(res, item)

        item['price'] = price
        item['descrition'] = descrition
        item['market_stats'] = market_stats
        item['price_history_date'] = price_history_date
        item['title'] = title

        item['bigAddress'] = bigAddress
        item['id'] = id

        print(item)
        return item
    except Exception as e:
        write_error(id)
        print('解析错误', e)


def get_detail_info(idList, bigAddress, page, pages, addressNumber):
    data_list = []
    greenlets = [gevent.spawn(openlink, 'https://www.zoopla.co.uk/to-rent/details/%s' % id, headers,
                              'id: %s\%s page: %s\%s address: %s\%s(%s)' % (
                                  idList.index(id) + 1, len(idList), page, pages, addressNumber, len(address_list),
                                  bigAddress)) for id in idList]
    gevent.joinall(greenlets)
    response_list = [a.value for a in greenlets]
    for detail_res in response_list:
        id = ''.join(re.findall("\d+\.?\d*", detail_res.url))
        # detail_res = openlink(detail_url, headers)
        data_list.append(parse(detail_res, bigAddress, id))
    save_data(data_list, bigAddress)


def save_data(data_list, bigAddress):
    try:
        conditon = False
        if not os.path.exists(data_csv_dir + '/' + bigAddress + '.csv'):
            conditon = True
        with open(data_csv_dir + '/' + bigAddress + '.csv', 'a', newline='') as f:  # file_path 是 csv 文件存储的路径
            fieldnames = filed
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if conditon:
                writer.writeheader()  # 写入头部，即设置列名
            for data in data_list:
                writer.writerow(data)
    except Exception as e:
        print('保存数据错误', e)
    else:
        print("添加数据成功,地名为%s" % bigAddress)


def crawl_main(bigAddress):
    # address = 'Bexley (London Borough), London'
    try:
        addressNumber = address_list.index(bigAddress) + 1
        page = '1'
        url = 'https://www.zoopla.co.uk/search/?q=%s&geo_autocomplete_identifier=&price_min=&price_max=&property_type=&beds_min=&category=residential&price_frequency=per_month&furnished_state=&radius=&added=&results_sort=newest_listings&keywords=&new_homes=&retirement_homes=true&shared_ownership=&include_auctions=true&include_sold=&include_shared_accommodation=false&include_rented=true&search_source=to-rent&section=to-rent&view_type=list'
        info = 'address: %s\%s(%s)' % (addressNumber, len(address_list), bigAddress)
        res = openlink(url % (quote(bigAddress)), headers, info)
        tree = etree.HTML(res.text)
        idList = tree.xpath("//*[@class='srp clearfix   ']/@data-listing-id")
        pageList = tree.xpath("//div[@class='paginate bg-muted']/a/text()")
        pages = int(pageList[-2])
        get_detail_info(idList, bigAddress, page, pages, addressNumber)
        greenlets = [gevent.spawn(openlink, res.url + "&pn=%s" % str(page), headers,
                                  'page: %s\%s  address: %s\%s(%s)' % (
                                      page, pages, addressNumber, len(address_list), bigAddress)) for page in
                     range(2, pages)]
        gevent.joinall(greenlets)
        response_list = [a.value for a in greenlets]
        for rommList_res in response_list:
            # list_url=res.url+"&pn=%s"%str(page)
            # rommList_res = openlink(list_url, headers)
            tree = etree.HTML(rommList_res.text)
            idList = tree.xpath("//*[@class='srp clearfix   ']/@data-listing-id")
            get_detail_info(idList, bigAddress, page, pages, addressNumber)
    except Exception as e:
        write_error(str(bigAddress))
        print(e)


def openlink(url, headers, info):
    """
    """
    maxTryNum = 15
    use_proxy = True
    use_delay = False
    for tries in range(maxTryNum):
        if use_delay:
            sleep_time = random.random(1.5)
            print('延迟%s秒' % (str(sleep_time)))
            time.sleep(sleep_time)
        try:
            if use_proxy:
                proxy = get_proxy()
                print(info, '爬取 %s,使用代理 %s' % (url, proxy))
                response = requests.get(url, headers=headers, proxies={'http': proxy})
                return response
            else:
                print(info, '爬取 %s' % url)
                response = requests.get(url, headers=headers)
                return response
        except:
            if tries < (maxTryNum - 1):
                continue
            else:
                print("尝试%d 次连接网址%s失败!" % (maxTryNum, url))


def get_proxy():
    response = requests.get('http://127.0.0.1:5010/get/')
    return 'http://' + response.text


def csv_to_excel():
    files = os.listdir(data_csv_dir)
    for file in files:
        data = pd.read_csv(data_csv_dir + '/' + file)
        data.to_excel(data_xlsx_dir + '/' + file.split('.')[0] + '.xlsx', index=False)


def create_data_dir(data_dir):
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)


def write_error(info):
    with open('error', 'a') as f:
        f.write(str(info))


if __name__ == '__main__':
    concurrency_num = 10
    data_csv_dir = 'csv'
    data_xlsx_dir = 'xlsx'
    headers = {  # User-Agent需要根据每个人的电脑来修改，每个人的信息是不同的
        'Accept': '*/*',
        'Accept-Encoding': 'br',
        'Accept-Language': 'zh,en-GB;q=0.9,en;q=0.8,en-US;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3423.2 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
    }
    '45329573'
    create_data_dir(data_csv_dir)
    create_data_dir(data_xlsx_dir)
    address_list = [
        "Barking and Dagenham (London Borough), London",
        "Barnet (London Borough), London",
        "Bexley (London Borough), London",
        "Brent (London Borough), London ",
        "Bromley (London Borough), London ",
        "Camden (London Borough), London ",
        "City of London (London Borough), London",
        "Croydon (London Borough), London ",
        "Ealing (London Borough), London ",
        "Enfield (London Borough), London",
        "Greenwich (Royal Borough), London",
        "Hackney (London Borough), London ",
        "Hammersmith and Fulham (London Borough), London ",
        "Haringey (London Borough), London ",
        "Harrow (London Borough), London ",
        "Havering (London Borough), London ",
        "Hillingdon (London Borough), London ",
        "Hounslow (London Borough), London",
        "Islington (London Borough), London",
        "Kensington and Chelsea (Royal Borough), London",
        "Kingston upon Thames (Royal Borough), London ",
        "Lambeth (London Borough), London ",
        "Lewisham (London Borough), London ",
        "Merton (London Borough), London ",
        "Newham (London Borough), London ",
        "Redbridge (London Borough), London",
        "Richmond upon Thames (London Borough), London",
        "Southwark (London Borough), London ",
        "Sutton (London Borough), London ",
        "Tower Hamlets (London Borough), London",
        "Waltham Forest (London Borough), London ",
        "Wandsworth (London Borough), London ",
        "Westminster (London Borough), London"]
    # ]
    filed = ['has_modern_etc', 'latitude_min', 'country_code', 'region_name', 'market_stats', 'latitude',
             'agentAddress', 'has_house', 'incode', 'longitude_min', 'county_area_name', 'num_baths', 'furnished_state',
             'is_shared_ownership', 'has_garden', 'descrition', 'price', 'num_recepts', 'longitude_max',
             'property_type', 'bigAddress', 'has_floorplan', 'has_flat_studio', 'school_distance', 'title', 'longitude',
             'area_name', 'zindex', 'is_retirement_home', 'room_status', 'price_history_date', 'agentName', 'outcode',
             'num_beds', 'brand_name', 'id', 'branch_name', 'has_epc', 'post_town_name', 'room_condition',
             'subway_distance', 'postal_area', 'display_address', 'latitude_max', 'agentPhone', 'room_category']
    p = Pool(len(address_list))
    for bigAddress in address_list:
        p.apply_async(crawl_main, args={bigAddress, })
    p.close()
    p.join()
    csv_to_excel()
