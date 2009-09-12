(function() {
    var links = document.getElementsByTagName('a');
    var query = '?';
    for (var i = 0; i < links.length; i++) {
	if (links[i].href.indexOf('#disqus_thread') >= 0) {
	    query += 'url' + i + '=' + encodeURIComponent(links[i].href) + '&';
	}
    }
    document.write('<' + 'script type="text/javascript" src="http://disqus.com/forums/brettaylor/get_num_replies.js' + query + '"></' + 'script>');
})();
