#!/usr/bin/env python
# coding: utf-8
"""Script to download the newest online invoices from German telco provider Alice.
Ignores already existing ones."""

__appname__ = "Alice Invoices"
__author__  = "Christoph Matthies"
__version__ = "0.1"
__license__ = "GNU GPL 3.0 or later"

import logging, argparse, sys, os, re, string

try:
	import mechanize
except ImportError:
	print sys.exit("Error: module 'mechanize' can't be found.")

try:
	from bs4 import BeautifulSoup
except ImportError:
	print sys.exit("Error: module 'bs4' can't be found.\nInstall BeautifulSoup.")

from urllib2 import URLError

log = logging.getLogger(__name__)

class AliceInvoiceDownloader(mechanize.Browser):

	def __init__(self, *args, **kwargs):
		mechanize.Browser.__init__(self, *args, **kwargs)
		self.login_url = 	"https://dsl.o2online.de/sso/login?service=\
							https://dsl.o2online.de/selfcare/content/\
							segment/kundencenter/secured/".translate(None,string.whitespace)
		self.login_form_name = "fm1"
		self.invoice_overview_url = "https://dsl.o2online.de/selfcare/\
									content/segment/kundencenter/daten-vertraege/\
									rechnung/monatsuebersicht/".translate(None,string.whitespace)
		self.url_template= 'https://rechnung.dsl.o2online.de/asp/\
							DAIW_download_PDF.asp?\
							numero_fattura={numero_fattura}&\
							anno={anno}&\
							mese={mese}&\
							p1={p1}&\
							data_emissione={data_emissione}&\
							doc_row_id={doc_row_id}&\
							num_pagine_fattura={num_pagine_fattura}&\
							offset_inizio_fatt={offset_inizio_fatt}&\
							flgTr={flgTr}&\
							ente_fattura={ente_fattura}'.translate(None,string.whitespace)
							#https://rechnung.dsl.o2online.de/asp/DAIW_download_PDF.asp
							#?numero_fattura=&M123456789123456
							#anno=2000&
							#mese=01&
							#p1=133123456&
							#data_emissione=01.01.2000&
							#doc_row_id=1341234&
							#num_pagine_fattura=10&
							#offset_inizio_fatt=57&
							#flgTr=S&
							#ente_fattura=5
		log.debug("Instantiated: " + repr(self))

	def start_download(self, folder, username, password):
		try:
			self._login(url = self.login_url,
						form_name = self.login_form_name,
						username = username,
						password = password)
			urls = self._get_pdf_urls(self.invoice_overview_url)
			self._download_files(urls=urls, folder=folder)
		except URLError as e:
			sys.exit("Error: {!s}. Maybe no internet connectivity?".format(e.reason)) 

	def _login(self, url, form_name, username, password):
		self.open(url)
		log.debug("Opened " + url)
		self.select_form(name=form_name)
		log.debug("Selected form " + form_name)
		self["username"] = username
		self["password"] = password
		response = self.submit()
		log.debug("Submitted form " + form_name)
		if "ungültig" in response.get_data():
			sys.exit("Error: username and/or password were not accepted.")

	def _get_pdf_urls(self, url):
		log.debug("Opening " + self.invoice_overview_url)
		response = self.open(self.invoice_overview_url)
		soup = BeautifulSoup(response.read())
		iframe_url = soup.find("iframe", {"id":"invoice"})["src"]
		log.debug("Opening " + iframe_url)
		response2 = self.open(iframe_url)
		soup = BeautifulSoup(response2.read())
		frame_url = soup.find("frame")["src"]
		log.debug("Opening " + frame_url)
		response3 = self.open(frame_url)
		soup = BeautifulSoup(response3.read())

		anchors = soup.find_all(name="a", text="PDF", attrs={'href':re.compile("javascript:")})
		log.debug("{!s} PDF links found.".format(len(anchors)))
		links = [link["href"] for link in anchors]
		download_data = [link[19:-1].replace("'","").replace(" ", "").split(",") for link in links]

		urls = []
		for data in download_data:
			urls.append(self.url_template.format(
			numero_fattura = data[1],
			anno = data[2],
			mese = data[3],
			p1 = data[9],
			data_emissione = data[4],
			doc_row_id = data[5],
			num_pagine_fattura = data[6],
			offset_inizio_fatt = data[7],
			flgTr = data[8],
			ente_fattura = data[10]))
		return urls


	def _download_files(self, urls, folder):
		file_paths = []
		for url in urls:
			response = self.open(url)
			filename = response.info()["Content-Disposition"].split('=')[1]
			location = os.path.join(folder, filename)
			if os.path.exists(location):
				log.info("File '{0}' already exists. Skipping.".format(location))
				continue
			f = open(location, 'w')
			f.write(response.read())
			log.info("Saved file '{0}'".format(location))
			file_paths.append(location)
		if len(file_paths) == 0:
			print "No new files were available."
		else:
			print "The following {0} downloaded:".format(
					"{0} new files were".format(len(file_paths)) if len(file_paths)>1 \
						else "new file was")
			for path in file_paths:
				print os.path.abspath(path)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description=__doc__)
	group = parser.add_mutually_exclusive_group()
	group.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity. Supply twice for increased effect.")
	group.add_argument("-q", "--quiet", action="count", default=0, help="Decrease verbosity. Supply twice for increased effect.")
	parser.add_argument('--version', action='version', version='%s %s by %s. License: %s' % (__appname__, __version__, __author__, __license__))
	parser.add_argument('folder', action="store", help="The folder where invoices will be stored.")
	parser.add_argument('uname', action="store", help="The Alice username.")
	parser.add_argument('pw', action="store", help="The Alice password.")
	args = parser.parse_args()

	log_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
	log_index = 2 + (args.verbose if args.verbose<=2 else 2) - (args.quiet if args.quiet<=2 else 2)

	logging.basicConfig(level=log_levels[log_index], 
						format='%(module)s %(levelname)s %(asctime)s %(message)s', 
						datefmt='%d.%m.%y %H:%M:%S')

	# mechanize_log = logging.getLogger("mechanize")
	# mechanize_log.setLevel(log_levels[log_index])

	log.debug('CLI arguments: %s' % args)

	log.info('Starting.')

	AliceInvoiceDownloader().start_download(folder=args.folder, username=args.uname, password=args.pw)
