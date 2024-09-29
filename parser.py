import httpx
from bs4 import BeautifulSoup


def fetch(url: str) -> str:
    response = httpx.get(url)
    return response.text

def clear_escape_sequence(text: str) -> str:
    return text.replace('\n', '').replace('\t', '').replace('\r', '').replace('  ', '')

def get_products_links(url: str, max_pages: int | None) -> list[str]:
    products_links = []
    page = 1
    while True:
        print(f'Page {page} is parsing...')
        html = fetch(url=url + '?page=' + str(page))
        soup = BeautifulSoup(html, 'html.parser')

        alert_div = soup.find('div', {'class': 'alert alert-warning'})
        if alert_div is not None:
            break

        products = soup.find('div', {'id': 'product-grid'})
        products_thumbs = products.find_all('div', {'class': 'product_thumb'})
        products_a_tags = [product_thumb.find('a') for product_thumb in products_thumbs]
        products_links += ['https://cwspirits.com' + product['href'] for product in products_a_tags]
        
        page += 1
        if max_pages and page > max_pages:
            break

    return products_links


def get_product_info(url: str, type_name: str) -> dict:
    html = fetch(url=url)
    soup = BeautifulSoup(html, 'html.parser')

    try:
        item_img_div = soup.find('div', {'class': 'main-product-image'})
        item_img = item_img_div.find('img')
        item_img_url = item_img['src']
        item_img_url = 'https:' + item_img_url

        product_info_div = soup.find('div', {'class': 'product-info-main'})
        product_title = product_info_div.find('h1')
        product_title = product_title.text.strip()

        product_brand_name = product_info_div.find('div', {'class': 'product-brand-name'})
        product_brand_name_span = product_brand_name.find('span')
        product_brand_name = product_brand_name_span.text.strip()

        product_price_div = soup.find('div', {'class': 'product-price'})
        product_price = product_price_div.text.strip().replace('$', '')

        # Description and details
        site_content_divs = soup.find_all('div', {'class': 'site_content'})

        description = None
        alcohol_volume = None
        country = None
        volume = None
        if site_content_divs and len(site_content_divs) > 1:
            description_div = site_content_divs[0]
            description_div_p = description_div.find('p')
            description = description_div_p.text.strip()

            product_details_div = site_content_divs[1].find('ul')
            for li in product_details_div.find_all('li'):
                if 'ABV' in li.text:
                    alcohol_volume = li.text.strip().replace('ABV:' , '').strip()
                elif 'Region' in li.text:
                    country = li.text.strip().replace('Region:', '').strip()
                elif 'Bottle Size' in li.text:
                    volume = li.text.strip().replace('Bottle Size:', '').strip()

        product_info = dict(
            title=product_title,
            image_url=item_img_url,
            description=description,
            type_name=type_name,
            price=product_price,
            volume=volume,
            alcohol_volume=alcohol_volume,
            origin_country_name=country,
            brand_name=product_brand_name,
        )

        return product_info, None

    except Exception as e:
        return None, f'Error: {e}'
    

def parse_alcohol_section(url: str, type_name: str, max_pages: int | None = None, max_products: int | None = None) -> list[dict]:
    products_links = get_products_links(url=url, max_pages=max_pages)

    products_info = []
    products_links_num = max_products if max_products and max_products < len(products_links) else len(products_links)
    for i in range(products_links_num):
        if max_products and i > max_products:
            break
        product_info, error_message = get_product_info(url=products_links[i], type_name=type_name)
        if product_info:
            products_info.append(product_info)
            print(f'Parsed item {i+1} of {products_links_num}')
        else:
            print(f'Skipped item {i+1} of {products_links_num}: {error_message}')

    return products_info
