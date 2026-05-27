// Runs on every instagram.com page.
// Responds to messages from the popup to extract profile data.

const IG_APP_ID = "936619743392459";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action === "extractProfile") {
    extractProfile(msg.username)
      .then(sendResponse)
      .catch(err => sendResponse({ error: err.message }));
    return true; // keep channel open for async response
  }
});

async function extractProfile(username) {
  const user = await fetchProfileInfo(username);

  if (user.is_private) {
    return {
      username,
      full_name: user.full_name || "",
      profile_pic_url: user.profile_pic_url || "",
      follower_count: user.edge_followed_by?.count || 0,
      is_private: true,
    };
  }

  const postEdges = user.edge_owner_to_timeline_media?.edges || [];
  const posts = postEdges.slice(0, 9).map(edge => {
    const node = edge.node;
    const caption = node.edge_media_to_caption?.edges?.[0]?.node?.text || "";
    const imgUrl =
      node.thumbnail_src || node.display_url ||
      node.resources?.[0]?.src || "";
    return { caption: caption.slice(0, 300), image_url: imgUrl };
  });

  const highlightTitles = await fetchHighlightTitles(user.id).catch(() => []);

  // Collect image URLs: profile pic + up to 6 post thumbnails
  const imageUrls = [
    user.profile_pic_url_hd || user.profile_pic_url,
    ...posts.map(p => p.image_url).filter(Boolean),
  ].filter(Boolean).slice(0, 7);

  const images = await downloadImages(imageUrls);

  return {
    username,
    full_name: user.full_name || "",
    biography: user.biography || "",
    follower_count: user.edge_followed_by?.count || 0,
    following_count: user.edge_follow?.count || 0,
    media_count: user.edge_owner_to_timeline_media?.count || 0,
    is_private: false,
    profile_pic_url: user.profile_pic_url_hd || user.profile_pic_url || "",
    posts,
    highlight_titles: highlightTitles,
    images,
  };
}

async function fetchProfileInfo(username) {
  const res = await fetch(
    `https://www.instagram.com/api/v1/users/web_profile_info/?username=${encodeURIComponent(username)}`,
    {
      headers: {
        "X-IG-App-ID": IG_APP_ID,
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "include",
    }
  );

  if (res.status === 401 || res.status === 403) {
    throw new Error("Non sei loggato su Instagram. Apri instagram.com e fai il login.");
  }
  if (res.status === 404) {
    throw new Error(`Utente @${username} non trovato`);
  }
  if (!res.ok) {
    throw new Error(`Errore Instagram (${res.status}). Riprova tra qualche secondo.`);
  }

  const data = await res.json();
  const user = data?.data?.user;
  if (!user) throw new Error("Profilo non trovato o non accessibile");
  return user;
}

async function fetchHighlightTitles(userId) {
  const res = await fetch(
    `https://www.instagram.com/api/v1/highlights/${userId}/highlights_tray/`,
    {
      headers: {
        "X-IG-App-ID": IG_APP_ID,
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "include",
    }
  );
  if (!res.ok) return [];
  const data = await res.json();
  const trays = data?.tray || [];
  return trays.map(t => t.title).filter(Boolean).slice(0, 10);
}

async function downloadImages(urls) {
  const results = await Promise.allSettled(
    urls.map(async url => {
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("download failed");
      const blob = await res.blob();
      const base64 = await blobToBase64(blob);
      const mediaType = blob.type || "image/jpeg";
      return { data: base64, media_type: mediaType };
    })
  );
  return results
    .filter(r => r.status === "fulfilled")
    .map(r => r.value);
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
